// Prism-ANN v3 Native C++17 / ARM NEON SIMD Kernel (ADR-0005)
// ===========================================================
// Implements:
//   1. prism_mode3_scan_ranges_f32  -- Zero-copy CRoaring [start, end) FP32 NEON scan
//   2. prism_mode3_scan_ranges_sq8  -- Zero-copy CRoaring [start, end) SQ8 vdotq_s32 + FP32 rerank
//   3. prism_search_hhnsw_gls       -- Native H-HNSW v2 + ACORN-GLS + Local-Stall Guard
//   4. Bitset helpers               -- O(N_cand/64) range set/clear & byte-mask packing
//
// Build (Apple Silicon / macOS):
//   clang++ -O3 -mcpu=native -std=c++17 -shared -fPIC \
//       bench/prism_ckernel.cpp -o bench/_build/libprism_ckernel.dylib

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <queue>
#include <utility>
#include <vector>

#if defined(__ARM_NEON) || defined(__aarch64__)
#include <arm_neon.h>
#define PRISM_HAS_NEON 1
#else
#define PRISM_HAS_NEON 0
#endif

namespace {

// ---------------------------------------------------------------------------
// SIMD Inner Product Kernels (ARM NEON with portable scalar fallback)
// ---------------------------------------------------------------------------
static inline float dot_f32(const float* __restrict a, const float* __restrict b, int32_t d) {
#if PRISM_HAS_NEON
    float32x4_t acc0 = vdupq_n_f32(0.0f);
    float32x4_t acc1 = vdupq_n_f32(0.0f);
    float32x4_t acc2 = vdupq_n_f32(0.0f);
    float32x4_t acc3 = vdupq_n_f32(0.0f);
    int32_t i = 0;
    for (; i + 16 <= d; i += 16) {
        acc0 = vfmaq_f32(acc0, vld1q_f32(a + i),      vld1q_f32(b + i));
        acc1 = vfmaq_f32(acc1, vld1q_f32(a + i + 4),  vld1q_f32(b + i + 4));
        acc2 = vfmaq_f32(acc2, vld1q_f32(a + i + 8),  vld1q_f32(b + i + 8));
        acc3 = vfmaq_f32(acc3, vld1q_f32(a + i + 12), vld1q_f32(b + i + 12));
    }
    acc0 = vaddq_f32(vaddq_f32(acc0, acc1), vaddq_f32(acc2, acc3));
    for (; i + 4 <= d; i += 4) {
        acc0 = vfmaq_f32(acc0, vld1q_f32(a + i), vld1q_f32(b + i));
    }
    float sum = vaddvq_f32(acc0);
    for (; i < d; ++i) {
        sum += a[i] * b[i];
    }
    return sum;
#else
    float sum = 0.0f;
    for (int32_t i = 0; i < d; ++i) {
        sum += a[i] * b[i];
    }
    return sum;
#endif
}

static inline int32_t dot_sq8(const int8_t* __restrict a, const int8_t* __restrict b, int32_t d) {
#if PRISM_HAS_NEON && defined(__ARM_FEATURE_DOTPROD)
    int32x4_t acc0 = vdupq_n_s32(0);
    int32x4_t acc1 = vdupq_n_s32(0);
    int32x4_t acc2 = vdupq_n_s32(0);
    int32x4_t acc3 = vdupq_n_s32(0);
    int32_t i = 0;
    for (; i + 64 <= d; i += 64) {
        acc0 = vdotq_s32(acc0, vld1q_s8(a + i),      vld1q_s8(b + i));
        acc1 = vdotq_s32(acc1, vld1q_s8(a + i + 16), vld1q_s8(b + i + 16));
        acc2 = vdotq_s32(acc2, vld1q_s8(a + i + 32), vld1q_s8(b + i + 32));
        acc3 = vdotq_s32(acc3, vld1q_s8(a + i + 48), vld1q_s8(b + i + 48));
    }
    acc0 = vaddq_s32(vaddq_s32(acc0, acc1), vaddq_s32(acc2, acc3));
    for (; i + 16 <= d; i += 16) {
        acc0 = vdotq_s32(acc0, vld1q_s8(a + i), vld1q_s8(b + i));
    }
    int32_t sum = vaddvq_s32(acc0);
    for (; i < d; ++i) {
        sum += static_cast<int32_t>(a[i]) * static_cast<int32_t>(b[i]);
    }
    return sum;
#elif PRISM_HAS_NEON
    int32x4_t acc0 = vdupq_n_s32(0);
    int32x4_t acc1 = vdupq_n_s32(0);
    int32_t i = 0;
    for (; i + 16 <= d; i += 16) {
        int8x16_t va = vld1q_s8(a + i);
        int8x16_t vb = vld1q_s8(b + i);
        int16x8_t p_lo = vmull_s8(vget_low_s8(va), vget_low_s8(vb));
        int16x8_t p_hi = vmull_s8(vget_high_s8(va), vget_high_s8(vb));
        acc0 = vpadalq_s16(acc0, p_lo);
        acc1 = vpadalq_s16(acc1, p_hi);
    }
    int32_t sum = vaddvq_s32(vaddq_s32(acc0, acc1));
    for (; i < d; ++i) {
        sum += static_cast<int32_t>(a[i]) * static_cast<int32_t>(b[i]);
    }
    return sum;
#else
    int32_t sum = 0;
    for (int32_t i = 0; i < d; ++i) {
        sum += static_cast<int32_t>(a[i]) * static_cast<int32_t>(b[i]);
    }
    return sum;
#endif
}

// ---------------------------------------------------------------------------
// Compact Fixed-Capacity Min-Heap for Top-K Tracking (zero per-item allocs)
// ---------------------------------------------------------------------------
template <typename ScoreT>
struct TopKHeap {
    struct Entry {
        ScoreT score;
        int32_t id;
    };
    int32_t cap;
    std::vector<Entry> data;

    explicit TopKHeap(int32_t capacity) : cap(capacity) {
        data.reserve(static_cast<size_t>(std::max(1, capacity)));
    }

    static inline bool worse_than(const Entry& a, const Entry& b) {
        // Min-heap root is the WORST entry (smallest score; tie-break larger id as worse)
        return (a.score < b.score) || (a.score == b.score && a.id > b.id);
    }

    inline bool full() const { return static_cast<int32_t>(data.size()) >= cap; }
    inline ScoreT min_score() const { return data[0].score; }

    inline void sift_up(int32_t idx) {
        while (idx > 0) {
            int32_t parent = (idx - 1) >> 1;
            if (worse_than(data[idx], data[parent])) {
                std::swap(data[idx], data[parent]);
                idx = parent;
            } else {
                break;
            }
        }
    }

    inline void sift_down(int32_t idx) {
        int32_t n = static_cast<int32_t>(data.size());
        while (true) {
            int32_t left = (idx << 1) + 1;
            int32_t right = left + 1;
            int32_t smallest = idx;
            if (left < n && worse_than(data[left], data[smallest])) {
                smallest = left;
            }
            if (right < n && worse_than(data[right], data[smallest])) {
                smallest = right;
            }
            if (smallest != idx) {
                std::swap(data[idx], data[smallest]);
                idx = smallest;
            } else {
                break;
            }
        }
    }

    inline void push(ScoreT score, int32_t id) {
        if (cap <= 0) return;
        Entry e{score, id};
        if (static_cast<int32_t>(data.size()) < cap) {
            data.push_back(e);
            sift_up(static_cast<int32_t>(data.size()) - 1);
        } else if (worse_than(data[0], e)) {
            data[0] = e;
            sift_down(0);
        }
    }

    void sort_descending() {
        std::sort(data.begin(), data.end(), [](const Entry& a, const Entry& b) {
            if (a.score != b.score) return a.score > b.score;
            return a.id < b.id;
        });
    }
};

// ---------------------------------------------------------------------------
// Bitset helpers (uint64_t array of length ceil(N/64))
// ---------------------------------------------------------------------------
static inline bool bit_test(const uint64_t* bits, int32_t idx) {
    return ((bits[idx >> 6] >> (idx & 63)) & 1ULL) != 0ULL;
}

static inline void set_range_bits(uint64_t* bits, int32_t s, int32_t e) {
    if (s >= e) return;
    int32_t w_s = s >> 6;
    int32_t w_e = (e - 1) >> 6;
    int32_t b_s = s & 63;
    int32_t b_e = (e - 1) & 63;
    if (w_s == w_e) {
        uint64_t mask = (~0ULL << b_s) & (~0ULL >> (63 - b_e));
        bits[w_s] |= mask;
    } else {
        bits[w_s] |= (~0ULL << b_s);
        for (int32_t w = w_s + 1; w < w_e; ++w) {
            bits[w] = ~0ULL;
        }
        bits[w_e] |= (~0ULL >> (63 - b_e));
    }
}

static inline void clear_range_bits(uint64_t* bits, int32_t s, int32_t e) {
    if (s >= e) return;
    int32_t w_s = s >> 6;
    int32_t w_e = (e - 1) >> 6;
    int32_t b_s = s & 63;
    int32_t b_e = (e - 1) & 63;
    if (w_s == w_e) {
        uint64_t mask = (~0ULL << b_s) & (~0ULL >> (63 - b_e));
        bits[w_s] &= ~mask;
    } else {
        bits[w_s] &= ~(~0ULL << b_s);
        for (int32_t w = w_s + 1; w < w_e; ++w) {
            bits[w] = 0ULL;
        }
        bits[w_e] &= ~(~0ULL >> (63 - b_e));
    }
}

// O(|ranges|) bounded portal sampling across CRoaring [start, end) intervals
static int32_t sample_portals_from_ranges(
    const int32_t* starts,
    const int32_t* ends,
    int32_t n_ranges,
    int32_t N,
    int32_t max_portals,
    int32_t* out_portals
) {
    if (n_ranges <= 0 || max_portals <= 0) return 0;
    int64_t total = 0;
    for (int32_t r = 0; r < n_ranges; ++r) {
        int32_t s = std::max(0, starts[r]);
        int32_t e = std::min(N, ends[r]);
        if (e > s) total += static_cast<int64_t>(e - s);
    }
    if (total <= 0) return 0;

    int32_t k_portals = static_cast<int32_t>(std::min<int64_t>(max_portals, total));
    int64_t targets[8];
    if (k_portals > 8) k_portals = 8;
    for (int32_t j = 0; j < k_portals; ++j) {
        // Evenly spaced midpoints across the total authorized cardinality
        targets[j] = (static_cast<int64_t>(j) * total + total / 2) / k_portals;
        if (targets[j] >= total) targets[j] = total - 1;
    }

    int32_t out_cnt = 0;
    int64_t cum = 0;
    int32_t t_idx = 0;
    for (int32_t r = 0; r < n_ranges && t_idx < k_portals; ++r) {
        int32_t s = std::max(0, starts[r]);
        int32_t e = std::min(N, ends[r]);
        if (e <= s) continue;
        int64_t len = static_cast<int64_t>(e - s);
        while (t_idx < k_portals && targets[t_idx] < cum + len) {
            int32_t cand = s + static_cast<int32_t>(targets[t_idx] - cum);
            if (out_cnt == 0 || out_portals[out_cnt - 1] != cand) {
                out_portals[out_cnt++] = cand;
            }
            ++t_idx;
        }
        cum += len;
    }
    return out_cnt;
}

}  // namespace

extern "C" {

struct PrismSearchStats {
    int64_t dist_computations;
    int32_t hops_1hop;
    int32_t hops_2hop;
    int32_t hops_teleport;
    int32_t expansions;
    int32_t n_auth_found;
    int32_t stalled;
    float mean_s_loc_hat;
    float early_s_loc_hat;
};

int32_t prism_kernel_has_neon() {
#if PRISM_HAS_NEON
    return 1;
#else
    return 0;
#endif
}

int32_t prism_kernel_has_dotprod() {
#if PRISM_HAS_NEON && defined(__ARM_FEATURE_DOTPROD)
    return 1;
#else
    return 0;
#endif
}

void prism_ranges_set_bitset(
    const int32_t* starts,
    const int32_t* ends,
    int32_t n_ranges,
    uint64_t* mask_bits,
    int32_t N
) {
    for (int32_t r = 0; r < n_ranges; ++r) {
        int32_t s = std::max(0, starts[r]);
        int32_t e = std::min(N, ends[r]);
        set_range_bits(mask_bits, s, e);
    }
}

void prism_ranges_clear_bitset(
    const int32_t* starts,
    const int32_t* ends,
    int32_t n_ranges,
    uint64_t* mask_bits,
    int32_t N
) {
    for (int32_t r = 0; r < n_ranges; ++r) {
        int32_t s = std::max(0, starts[r]);
        int32_t e = std::min(N, ends[r]);
        clear_range_bits(mask_bits, s, e);
    }
}

void prism_mask_bytes_to_bitset(
    const uint8_t* mask_bytes,
    uint64_t* mask_bits,
    int32_t N
) {
    int32_t n_words = (N + 63) >> 6;
    std::memset(mask_bits, 0, static_cast<size_t>(n_words) * sizeof(uint64_t));
    for (int32_t i = 0; i < N; ++i) {
        if (mask_bytes[i]) {
            mask_bits[i >> 6] |= (1ULL << (i & 63));
        }
    }
}

// ---------------------------------------------------------------------------
// Mode 3a: Zero-copy CRoaring [start, end) contiguous FP32 NEON scan
// ---------------------------------------------------------------------------
int64_t prism_mode3_scan_ranges_f32(
    const float* vectors,
    int32_t N,
    int32_t d,
    const float* query,
    const int32_t* starts,
    const int32_t* ends,
    int32_t n_ranges,
    int32_t k,
    int32_t* out_ids,
    float* out_scores
) {
    for (int32_t i = 0; i < k; ++i) {
        out_ids[i] = -1;
        out_scores[i] = -1e30f;
    }
    if (k <= 0 || n_ranges <= 0) return 0;

    TopKHeap<float> heap(k);
    int64_t total_evals = 0;
    const int64_t stride = static_cast<int64_t>(d);

    for (int32_t r = 0; r < n_ranges; ++r) {
        int32_t s = std::max(0, starts[r]);
        int32_t e = std::min(N, ends[r]);
        if (e <= s) continue;
        const float* vec = vectors + static_cast<int64_t>(s) * stride;
        for (int32_t id = s; id < e; ++id, vec += stride) {
            float sc = dot_f32(vec, query, d);
            if (!heap.full() || sc > heap.min_score()) {
                heap.push(sc, id);
            }
        }
        total_evals += static_cast<int64_t>(e - s);
    }

    heap.sort_descending();
    int32_t n_out = static_cast<int32_t>(heap.data.size());
    for (int32_t i = 0; i < n_out; ++i) {
        out_ids[i] = heap.data[i].id;
        out_scores[i] = heap.data[i].score;
    }
    return total_evals;
}

// ---------------------------------------------------------------------------
// Mode 3b: Zero-copy CRoaring [start, end) contiguous SQ8 NEON + FP32 rerank
// ---------------------------------------------------------------------------
int64_t prism_mode3_scan_ranges_sq8(
    const int8_t* sq8_vectors,
    const float* fp32_vectors,
    int32_t N,
    int32_t d,
    const int8_t* q_sq8,
    const float* q_fp32,
    const int32_t* starts,
    const int32_t* ends,
    int32_t n_ranges,
    int32_t k,
    int32_t rerank_k,
    int32_t* out_ids,
    float* out_scores
) {
    for (int32_t i = 0; i < k; ++i) {
        out_ids[i] = -1;
        out_scores[i] = -1e30f;
    }
    if (k <= 0 || n_ranges <= 0) return 0;
    int32_t rk = std::max(k, rerank_k);

    TopKHeap<int32_t> pre_heap(rk);
    int64_t total_evals = 0;
    const int64_t stride = static_cast<int64_t>(d);

    for (int32_t r = 0; r < n_ranges; ++r) {
        int32_t s = std::max(0, starts[r]);
        int32_t e = std::min(N, ends[r]);
        if (e <= s) continue;
        const int8_t* vec = sq8_vectors + static_cast<int64_t>(s) * stride;
        for (int32_t id = s; id < e; ++id, vec += stride) {
            int32_t sc = dot_sq8(vec, q_sq8, d);
            if (!pre_heap.full() || sc > pre_heap.min_score()) {
                pre_heap.push(sc, id);
            }
        }
        total_evals += static_cast<int64_t>(e - s);
    }

    if (pre_heap.data.empty()) return total_evals;

    // Exact FP32 rerank of top-rerank_k candidates
    TopKHeap<float> exact_heap(k);
    for (const auto& entry : pre_heap.data) {
        const float* vec = fp32_vectors + static_cast<int64_t>(entry.id) * stride;
        float sc = dot_f32(vec, q_fp32, d);
        exact_heap.push(sc, entry.id);
    }
    exact_heap.sort_descending();
    int32_t n_out = static_cast<int32_t>(exact_heap.data.size());
    for (int32_t i = 0; i < n_out; ++i) {
        out_ids[i] = exact_heap.data[i].id;
        out_scores[i] = exact_heap.data[i].score;
    }
    return total_evals;
}

// ---------------------------------------------------------------------------
// Native C++ H-HNSW v2 + ACORN-GLS + Local-Stall Guard Traversal
// ---------------------------------------------------------------------------
int32_t prism_search_hhnsw_gls(
    const float* vectors,
    int32_t N,
    int32_t d,
    int32_t entry_point,
    int32_t max_level,
    const int64_t* upper_offsets,
    const int32_t* upper_neighbors,
    const int32_t* cum_nn_per_lvl,
    const int32_t* base_neighbors,
    int32_t m_base,
    const int32_t* express_bridges,
    int32_t m_bridge,
    const uint64_t* mask_bits,
    const int32_t* starts,
    const int32_t* ends,
    int32_t n_ranges,
    const float* query,
    int32_t k,
    int32_t ef_search,
    float tau_high,
    float tau_low,
    int32_t use_express_bridges,
    int32_t use_portals,
    int32_t max_portals,
    int32_t use_gls_adaptive,
    int32_t faiss_style_1hop,
    float tau_stall,
    int32_t stall_check_hops,
    uint32_t* visited_epoch,
    uint32_t current_epoch,
    int32_t* out_ids,
    float* out_scores,
    PrismSearchStats* out_stats
) {
    for (int32_t i = 0; i < k; ++i) {
        out_ids[i] = -1;
        out_scores[i] = -1e30f;
    }
    PrismSearchStats stats{};
    if (N <= 0 || k <= 0) {
        if (out_stats) *out_stats = stats;
        return 0;
    }

    const int64_t stride = static_cast<int64_t>(d);
    auto score_node = [&](int32_t id) -> float {
        ++stats.dist_computations;
        return dot_f32(vectors + static_cast<int64_t>(id) * stride, query, d);
    };

    // 1. Upper-layer HNSW greedy zoom-in (levels max_level .. 1)
    int32_t ep = entry_point;
    float ep_sim = -1e30f;
    if (ep >= 0 && ep < N && upper_offsets && upper_neighbors && cum_nn_per_lvl && max_level >= 1) {
        ep_sim = score_node(ep);
        for (int32_t lvl = max_level; lvl >= 1; --lvl) {
            bool changed = true;
            while (changed) {
                changed = false;
                int64_t off = upper_offsets[ep];
                int64_t row_end = upper_offsets[ep + 1];
                int64_t beg = off + cum_nn_per_lvl[lvl];
                int64_t end = std::min(row_end, off + cum_nn_per_lvl[lvl + 1]);
                for (int64_t idx = beg; idx < end; ++idx) {
                    int32_t nb = upper_neighbors[idx];
                    if (nb < 0) break;
                    float sc = score_node(nb);
                    if (sc > ep_sim) {
                        ep_sim = sc;
                        ep = nb;
                        changed = true;
                    }
                }
            }
        }
    } else if (ep < 0 || ep >= N) {
        // Fallback: 16 uniform landmarks if no upper-layer CSR was supplied
        int32_t n_lm = std::min(16, N);
        int32_t step = std::max(1, N / n_lm);
        ep = 0;
        ep_sim = -1e30f;
        for (int32_t i = 0; i < N; i += step) {
            float sc = score_node(i);
            if (sc > ep_sim) {
                ep_sim = sc;
                ep = i;
            }
        }
    } else {
        ep_sim = score_node(ep);
    }

    // Candidate frontier (max-heap by similarity) + Authorized results (min-heap capped at max(ef_search, k))
    using Cand = std::pair<float, int32_t>;
    std::priority_queue<Cand> cand_queue;
    TopKHeap<float> results(std::max(ef_search, k));

    auto eval_and_push = [&](int32_t id, bool authorized_only) {
        if (id < 0 || id >= N) return;
        if (visited_epoch[id] == current_epoch) return;
        bool auth = bit_test(mask_bits, id);
        if (authorized_only && !auth) return;
        visited_epoch[id] = current_epoch;
        float sc = score_node(id);
        cand_queue.emplace(sc, id);
        if (auth) {
            results.push(sc, id);
            ++stats.n_auth_found;
        }
    };

    // Seed global upper-layer entry point (already scored as ep_sim)
    visited_epoch[ep] = current_epoch;
    cand_queue.emplace(ep_sim, ep);
    if (bit_test(mask_bits, ep)) {
        results.push(ep_sim, ep);
        ++stats.n_auth_found;
    }

    // Optional bounded authorized entry portals (k_0 <= 4) sampled in O(|ranges|)
    if (use_portals && max_portals > 0 && n_ranges > 0) {
        int32_t portals[8];
        int32_t np = sample_portals_from_ranges(
            starts, ends, n_ranges, N, std::min(max_portals, 4), portals
        );
        for (int32_t i = 0; i < np; ++i) {
            eval_and_push(portals[i], false);
        }
    }
    const int32_t n_auth_after_seed = stats.n_auth_found;

    // -----------------------------------------------------------------------
    // Mode A: Standard FAISS-style 1-hop filtered traversal (for E2 ablation)
    // -----------------------------------------------------------------------
    if (faiss_style_1hop) {
        int32_t max_exp = ef_search;
        while (!cand_queue.empty() && stats.expansions < max_exp) {
            auto [curr_sim, curr] = cand_queue.top();
            cand_queue.pop();
            if (results.full() && curr_sim < results.min_score()) {
                break;
            }
            ++stats.expansions;
            ++stats.hops_1hop;
            const int32_t* n1 = base_neighbors + static_cast<int64_t>(curr) * m_base;
            for (int32_t i = 0; i < m_base; ++i) {
                int32_t nb = n1[i];
                if (nb < 0) break;
                if (visited_epoch[nb] == current_epoch) continue;
                visited_epoch[nb] = current_epoch;
                float sc = score_node(nb);
                bool auth = bit_test(mask_bits, nb);
                if (!results.full() || sc > results.min_score()) {
                    cand_queue.emplace(sc, nb);
                }
                if (auth) {
                    results.push(sc, nb);
                    ++stats.n_auth_found;
                }
            }
        }
    } else {
        // -------------------------------------------------------------------
        // Mode B: H-HNSW v2 + ACORN-GLS + Local-Stall Guard
        // -------------------------------------------------------------------
        double s_loc_sum = 0.0;
        double early_s_loc_sum = 0.0;
        int32_t early_hops = 0;

        int32_t auth_buf[64];
        int32_t unauth_buf[64];
        int32_t m_cap = std::min(m_base, 64);

        while (!cand_queue.empty() && stats.expansions < ef_search) {
            auto [curr_sim, curr] = cand_queue.top();
            cand_queue.pop();
            if (results.full() && curr_sim < results.min_score()) {
                break;
            }
            ++stats.expansions;

            const int32_t* n1 = base_neighbors + static_cast<int64_t>(curr) * m_base;
            int32_t n_valid = 0;
            int32_t n_auth = 0;
            int32_t n_unauth = 0;
            for (int32_t i = 0; i < m_cap; ++i) {
                int32_t nb = n1[i];
                if (nb < 0) break;
                ++n_valid;
                if (bit_test(mask_bits, nb)) {
                    auth_buf[n_auth++] = nb;
                } else {
                    unauth_buf[n_unauth++] = nb;
                }
            }

            float s_loc_hat = (n_valid > 0) ? (static_cast<float>(n_auth) / static_cast<float>(n_valid)) : 0.0f;
            s_loc_sum += static_cast<double>(s_loc_hat);
            if (stats.expansions <= stall_check_hops) {
                early_s_loc_sum += static_cast<double>(s_loc_hat);
                ++early_hops;
            }

            // Determine ACORN-GLS mode
            int mode = 1;  // 0 = 1HOP, 1 = 2HOP, 2 = TELEPORT
            if (!use_gls_adaptive) {
                mode = 1;
            } else if (s_loc_hat >= tau_high) {
                mode = 0;
            } else if (s_loc_hat >= tau_low) {
                mode = 1;
            } else {
                mode = 2;
            }

            // Always evaluate unvisited authorized 1-hop base neighbors
            for (int32_t i = 0; i < n_auth; ++i) {
                eval_and_push(auth_buf[i], true);
            }

            if (mode == 0) {
                // Fast-path 1HOP: dense authorized region (s_loc_hat >= tau_high);
                // skip express bridges and 2-hop expansion to maximize evaluation savings.
                ++stats.hops_1hop;
            } else if (mode == 1) {
                ++stats.hops_2hop;
                // Evaluate authorized 1-hop & 2-hop Geometric Express Bridges
                if (use_express_bridges && express_bridges && m_bridge > 0) {
                    const int32_t* brs = express_bridges + static_cast<int64_t>(curr) * m_bridge;
                    for (int32_t i = 0; i < m_bridge; ++i) {
                        int32_t br = brs[i];
                        if (br < 0) continue;
                        eval_and_push(br, true);
                    }
                }
                // Expand authorized 2-hop neighbors through 1-hop hubs
                // In static 2-hop (!use_gls_adaptive), expand through ALL 1-hop neighbors (matches ACORN-1 2-hop);
                // in adaptive GLS, expand through unauthorized hubs (or all hubs if s_loc_hat < tau_high).
                const int32_t* hubs = (!use_gls_adaptive) ? n1 : unauth_buf;
                int32_t n_hubs = (!use_gls_adaptive) ? n_valid : n_unauth;
                for (int32_t h = 0; h < n_hubs; ++h) {
                    int32_t hub = hubs[h];
                    if (hub < 0) break;
                    const int32_t* n2 = base_neighbors + static_cast<int64_t>(hub) * m_base;
                    for (int32_t j = 0; j < m_base; ++j) {
                        int32_t cand2 = n2[j];
                        if (cand2 < 0) break;
                        if (visited_epoch[cand2] != current_epoch && bit_test(mask_bits, cand2)) {
                            eval_and_push(cand2, true);
                        }
                    }
                }
                // 2-hop express bridge expansion (authorized-only, zero wasted unauthorized evals)
                if (use_express_bridges && express_bridges && m_bridge > 0) {
                    const int32_t* brs = express_bridges + static_cast<int64_t>(curr) * m_bridge;
                    for (int32_t i = 0; i < m_bridge; ++i) {
                        int32_t br = brs[i];
                        if (br < 0) continue;
                        const int32_t* br2s = express_bridges + static_cast<int64_t>(br) * m_bridge;
                        for (int32_t j = 0; j < m_bridge; ++j) {
                            int32_t b2 = br2s[j];
                            if (b2 < 0) continue;
                            if (visited_epoch[b2] != current_epoch && bit_test(mask_bits, b2)) {
                                eval_and_push(b2, true);
                            }
                        }
                    }
                }
            } else {
                // TELEPORT mode (s_loc_hat < tau_low): 2-hop base + 1-hop & 2-hop Geometric Bridges
                ++stats.hops_teleport;
                if (use_express_bridges && express_bridges && m_bridge > 0) {
                    const int32_t* brs = express_bridges + static_cast<int64_t>(curr) * m_bridge;
                    for (int32_t i = 0; i < m_bridge; ++i) {
                        int32_t br = brs[i];
                        if (br < 0) continue;
                        eval_and_push(br, true);
                    }
                }
                for (int32_t h = 0; h < n_unauth; ++h) {
                    int32_t hub = unauth_buf[h];
                    const int32_t* n2 = base_neighbors + static_cast<int64_t>(hub) * m_base;
                    for (int32_t j = 0; j < m_base; ++j) {
                        int32_t cand2 = n2[j];
                        if (cand2 < 0) break;
                        if (visited_epoch[cand2] != current_epoch && bit_test(mask_bits, cand2)) {
                            eval_and_push(cand2, true);
                        }
                    }
                }
                if (use_express_bridges && express_bridges && m_bridge > 0) {
                    const int32_t* brs = express_bridges + static_cast<int64_t>(curr) * m_bridge;
                    for (int32_t i = 0; i < m_bridge; ++i) {
                        int32_t br = brs[i];
                        if (br < 0) continue;
                        // Expand 2-hop express bridges AND authorized base neighbors of authorized bridges
                        const int32_t* br2s = express_bridges + static_cast<int64_t>(br) * m_bridge;
                        for (int32_t j = 0; j < m_bridge; ++j) {
                            int32_t b2 = br2s[j];
                            if (b2 < 0) continue;
                            if (visited_epoch[b2] != current_epoch && bit_test(mask_bits, b2)) {
                                eval_and_push(b2, true);
                            }
                        }
                        if (bit_test(mask_bits, br)) {
                            const int32_t* b_n1 = base_neighbors + static_cast<int64_t>(br) * m_base;
                            for (int32_t j = 0; j < m_base; ++j) {
                                int32_t nb = b_n1[j];
                                if (nb < 0) break;
                                if (visited_epoch[nb] != current_epoch && bit_test(mask_bits, nb)) {
                                    eval_and_push(nb, true);
                                }
                            }
                        }
                    }
                }
                // Anti-starvation: if frontier is nearly empty (e.g., no-portal search in sparse pocket),
                // traverse up to 4 unauthorized base neighbors to keep moving toward q (never added to results!)
                if (cand_queue.size() < 4 && n_unauth > 0) {
                    int32_t pushed = 0;
                    for (int32_t h = 0; h < n_unauth && pushed < 4; ++h) {
                        int32_t hub = unauth_buf[h];
                        if (visited_epoch[hub] != current_epoch) {
                            eval_and_push(hub, false);
                            ++pushed;
                        }
                    }
                }
            }

            // Local-Stall Mode-3 Escalation Guard:
            // (a) Hop-1 depleted-entry detection (captures negative correlation r <= 0.5 even with portals):
            //     if the global upper-layer entry point `ep` is unauthorized, has s_loc_hat < tau_stall,
            //     and its entire 1-hop + 2-hop neighborhood yields < k authorized nodes -> stalled!
            if (tau_stall > 0.0f && stats.expansions == 1 && curr == ep) {
                int32_t ep_auth_2hop = stats.n_auth_found - n_auth_after_seed;
                if (!bit_test(mask_bits, ep) && s_loc_hat < tau_stall && ep_auth_2hop < k) {
                    stats.early_s_loc_hat = s_loc_hat;
                    stats.stalled = 1;
                    break;
                }
            }
            // (b) Early-hop sustained depletion guard (after stall_check_hops expansions)
            if (tau_stall > 0.0f && stall_check_hops > 0 && stats.expansions == stall_check_hops) {
                float early_mean = static_cast<float>(early_s_loc_sum / static_cast<double>(std::max(1, early_hops)));
                stats.early_s_loc_hat = early_mean;
                if (early_mean < tau_stall || stats.n_auth_found < k) {
                    stats.stalled = 1;
                    break;
                }
            }
        }

        stats.mean_s_loc_hat = (stats.expansions > 0)
            ? static_cast<float>(s_loc_sum / static_cast<double>(stats.expansions))
            : 0.0f;
        if (early_hops > 0 && stats.early_s_loc_hat == 0.0f) {
            stats.early_s_loc_hat = static_cast<float>(early_s_loc_sum / static_cast<double>(early_hops));
        }
        if (tau_stall > 0.0f && (stats.n_auth_found < k || stats.mean_s_loc_hat < tau_stall)) {
            stats.stalled = 1;
        }
    }

    results.sort_descending();
    int32_t n_out = std::min(k, static_cast<int32_t>(results.data.size()));
    for (int32_t i = 0; i < n_out; ++i) {
        out_ids[i] = results.data[i].id;
        out_scores[i] = results.data[i].score;
    }
    if (out_stats) *out_stats = stats;
    return n_out;
}

// ---------------------------------------------------------------------------
// Fast C++ Vamana / RNG-Diversity Geometric Bridge Selector per Bucket
// ---------------------------------------------------------------------------
// Given bucket vectors [n_b, d], global Z-IDs [n_b], top-K local candidate
// indices [n_b, K] sorted descending by similarity, and local medoid index,
// selects `n_slots` geometric navigable neighbors per node:
//   - Up to (n_slots - include_medoid) RNG-diverse semantic neighbors
//   - Optional 1 medoid hub link (or diverse spoke if node == medoid)
//   - Backfills remaining slots with top unused semantic neighbors
void prism_select_rng_bridges(
    const float* bucket_vecs,      // [n_b, d] L2-normalized FP32
    const int32_t* global_ids,     // [n_b] global Z-order IDs
    const int32_t* cand_local_ids, // [n_b, K] local indices sorted desc by sim (-1 invalid)
    const float* cand_sims,        // [n_b, K] similarity to node u
    int32_t n_b,
    int32_t d,
    int32_t K,
    int32_t n_slots,
    int32_t medoid_local,
    int32_t include_medoid,
    float rng_alpha,
    int32_t* out_global_bridges    // [n_b, n_slots] output global Z-IDs (-1 if empty)
) {
    if (n_b <= 0 || n_slots <= 0) return;
    const int64_t stride = static_cast<int64_t>(d);

    for (int32_t u = 0; u < n_b; ++u) {
        int32_t* dst = out_global_bridges + static_cast<int64_t>(u) * n_slots;
        for (int32_t s = 0; s < n_slots; ++s) dst[s] = -1;
        if (n_b <= 1) continue;

        const int32_t* cands = cand_local_ids + static_cast<int64_t>(u) * K;
        const float* csims = cand_sims + static_cast<int64_t>(u) * K;
        int32_t reserve_medoid = (include_medoid && n_slots >= 3 && medoid_local >= 0 && medoid_local < n_b && medoid_local != u) ? 1 : 0;
        int32_t rng_target = n_slots - reserve_medoid;

        int32_t sel_local[32];
        int32_t sel_cnt = 0;
        int32_t cap_slots = std::min(n_slots, 32);

        // Pass 1: RNG / Vamana diversity filter (alpha * sim(v, c) < sim(u, c))
        for (int32_t ci = 0; ci < K && sel_cnt < rng_target; ++ci) {
            int32_t c = cands[ci];
            if (c < 0 || c >= n_b || c == u) continue;
            bool dup = false;
            for (int32_t s = 0; s < sel_cnt; ++s) {
                if (sel_local[s] == c) { dup = true; break; }
            }
            if (dup) continue;
            float sim_uc = csims[ci];
            const float* vec_c = bucket_vecs + static_cast<int64_t>(c) * stride;
            bool occluded = false;
            for (int32_t s = 0; s < sel_cnt; ++s) {
                const float* vec_v = bucket_vecs + static_cast<int64_t>(sel_local[s]) * stride;
                float sim_vc = dot_f32(vec_v, vec_c, d);
                if (rng_alpha * sim_vc >= sim_uc) {
                    occluded = true;
                    break;
                }
            }
            if (!occluded) {
                sel_local[sel_cnt++] = c;
            }
        }

        // Optional medoid hub link (if not already selected)
        if (reserve_medoid && sel_cnt < cap_slots) {
            bool has_medoid = false;
            for (int32_t s = 0; s < sel_cnt; ++s) {
                if (sel_local[s] == medoid_local) { has_medoid = true; break; }
            }
            if (!has_medoid) {
                sel_local[sel_cnt++] = medoid_local;
            }
        }

        // Pass 2: Backfill remaining slots with highest-similarity unused candidates
        for (int32_t ci = 0; ci < K && sel_cnt < cap_slots; ++ci) {
            int32_t c = cands[ci];
            if (c < 0 || c >= n_b || c == u) continue;
            bool dup = false;
            for (int32_t s = 0; s < sel_cnt; ++s) {
                if (sel_local[s] == c) { dup = true; break; }
            }
            if (!dup) {
                sel_local[sel_cnt++] = c;
            }
        }

        for (int32_t s = 0; s < sel_cnt; ++s) {
            dst[s] = global_ids[sel_local[s]];
        }
    }
}

// ---------------------------------------------------------------------------
// Fast C++ Remapper for FAISS HNSW CSR (internal perm -> input Z-order space)
// ---------------------------------------------------------------------------
void prism_remap_hnsw_csr(
    const int64_t* offsets_int,
    const int32_t* neighbors_int,
    const int32_t* perm,       // perm[internal_id] = z_id
    const int32_t* inv_perm,   // inv_perm[z_id] = internal_id
    int32_t N,
    int32_t m_base,
    int64_t* out_offsets_z,    // [N + 1]
    int32_t* out_neighbors_z,  // [offsets_int[N]]
    int32_t* out_base_l0       // [N, m_base]
) {
    out_offsets_z[0] = 0;
    for (int32_t z = 0; z < N; ++z) {
        int32_t u_int = inv_perm[z];
        int64_t beg = offsets_int[u_int];
        int64_t end = offsets_int[u_int + 1];
        int64_t len = end - beg;
        int64_t dst_beg = out_offsets_z[z];
        out_offsets_z[z + 1] = dst_beg + len;

        int32_t* l0_dst = out_base_l0 + static_cast<int64_t>(z) * m_base;
        for (int32_t j = 0; j < m_base; ++j) l0_dst[j] = -1;

        for (int64_t k = 0; k < len; ++k) {
            int32_t nb_int = neighbors_int[beg + k];
            int32_t nb_z = (nb_int >= 0 && nb_int < N) ? perm[nb_int] : -1;
            out_neighbors_z[dst_beg + k] = nb_z;
            if (k < m_base) {
                l0_dst[k] = nb_z;
            }
        }
    }
}

}  // extern "C"
