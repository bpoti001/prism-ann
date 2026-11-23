// Prism-ANN v3.1 Reviewer Audit Micro-Ablation C++17 / ARM NEON Kernel
// =====================================================================
// Isolates each performance factor of Mode-3 Z-Ordered CRoaring scanning:
//   1. audit_scan_scattered_f32_scalar -- Non-Z-ordered IDs, scalar FP32
//   2. audit_scan_scattered_f32_neon   -- Non-Z-ordered IDs, ARM NEON FP32
//   3. audit_scan_zorder_f32_scalar    -- Contiguous CRoaring ranges, scalar FP32
//   4. audit_scan_zorder_f32_neon      -- Contiguous CRoaring ranges, ARM NEON FP32
//   5. audit_scan_zorder_sq8_scalar    -- Contiguous CRoaring ranges, scalar SQ8 + FP32 rerank
//   6. audit_scan_zorder_sq8_neon      -- Contiguous CRoaring ranges, ARM NEON vdotq_s32 + FP32 rerank
//   7. audit_flush_llc_cache           -- Evicts L1/L2/SLC cache lines via 64 MB stride-64 sweep
//
// Build (Apple Silicon / macOS):
//   clang++ -O3 -mcpu=native -std=c++17 -shared -fPIC \
//       -isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk \
//       bench/prism_audit_kernel.cpp -o bench/_build/libprism_audit_kernel.dylib

#include <algorithm>
#include <cstdint>
#include <vector>

#if defined(__ARM_NEON) || defined(__aarch64__)
#include <arm_neon.h>
#define PRISM_AUDIT_HAS_NEON 1
#else
#define PRISM_AUDIT_HAS_NEON 0
#endif

namespace {

static inline float dot_f32_scalar(const float* __restrict a, const float* __restrict b, int32_t d) {
    float sum = 0.0f;
#if defined(__clang__)
#pragma clang loop vectorize(disable) interleave(disable)
#endif
    for (int32_t i = 0; i < d; ++i) {
        sum += a[i] * b[i];
    }
    return sum;
}

static inline float dot_f32_neon(const float* __restrict a, const float* __restrict b, int32_t d) {
#if PRISM_AUDIT_HAS_NEON
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
    return dot_f32_scalar(a, b, d);
#endif
}

static inline int32_t dot_sq8_scalar(const int8_t* __restrict a, const int8_t* __restrict b, int32_t d) {
    int32_t sum = 0;
#if defined(__clang__)
#pragma clang loop vectorize(disable) interleave(disable)
#endif
    for (int32_t i = 0; i < d; ++i) {
        sum += static_cast<int32_t>(a[i]) * static_cast<int32_t>(b[i]);
    }
    return sum;
}

static inline int32_t dot_sq8_neon(const int8_t* __restrict a, const int8_t* __restrict b, int32_t d) {
#if PRISM_AUDIT_HAS_NEON && defined(__ARM_FEATURE_DOTPROD)
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
#elif PRISM_AUDIT_HAS_NEON
    int32x4_t acc0 = vdupq_n_s32(0);
    int32x4_t acc1 = vdupq_n_s32(0);
    int32_t i = 0;
    for (; i + 16 <= d; i += 16) {
        int8x16_t va = vld1q_s8(a + i);
        int8x16_t vb = vld1q_s8(b + i);
        acc0 = vpadalq_s16(acc0, vmull_s8(vget_low_s8(va), vget_low_s8(vb)));
        acc1 = vpadalq_s16(acc1, vmull_s8(vget_high_s8(va), vget_high_s8(vb)));
    }
    int32_t sum = vaddvq_s32(vaddq_s32(acc0, acc1));
    for (; i < d; ++i) {
        sum += static_cast<int32_t>(a[i]) * static_cast<int32_t>(b[i]);
    }
    return sum;
#else
    return dot_sq8_scalar(a, b, d);
#endif
}

template <typename ScoreT>
struct AuditTopKHeap {
    struct Entry {
        ScoreT score;
        int32_t id;
    };
    int32_t cap;
    std::vector<Entry> data;

    explicit AuditTopKHeap(int32_t capacity) : cap(capacity) {
        data.reserve(static_cast<size_t>(std::max(1, capacity)));
    }

    static inline bool worse_than(const Entry& a, const Entry& b) {
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
            if (left < n && worse_than(data[left], data[smallest])) smallest = left;
            if (right < n && worse_than(data[right], data[smallest])) smallest = right;
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

template <bool UseNeon>
static inline int64_t scan_scattered_f32_impl(
    const float* vectors,
    int32_t N,
    int32_t d,
    const float* query,
    const int32_t* ids,
    int32_t n_cand,
    int32_t k,
    int32_t* out_ids,
    float* out_scores
) {
    for (int32_t i = 0; i < k; ++i) {
        out_ids[i] = -1;
        out_scores[i] = -1e30f;
    }
    if (k <= 0 || n_cand <= 0) return 0;

    AuditTopKHeap<float> heap(k);
    const int64_t stride = static_cast<int64_t>(d);
    int64_t evals = 0;
    for (int32_t i = 0; i < n_cand; ++i) {
        int32_t id = ids[i];
        if (id < 0 || id >= N) continue;
        const float* vec = vectors + static_cast<int64_t>(id) * stride;
        float sc = UseNeon ? dot_f32_neon(vec, query, d) : dot_f32_scalar(vec, query, d);
        if (!heap.full() || sc > heap.min_score()) {
            heap.push(sc, id);
        }
        ++evals;
    }
    heap.sort_descending();
    int32_t n_out = static_cast<int32_t>(heap.data.size());
    for (int32_t i = 0; i < n_out; ++i) {
        out_ids[i] = heap.data[i].id;
        out_scores[i] = heap.data[i].score;
    }
    return evals;
}

template <bool UseNeon>
static inline int64_t scan_zorder_f32_impl(
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

    AuditTopKHeap<float> heap(k);
    const int64_t stride = static_cast<int64_t>(d);
    int64_t evals = 0;
    for (int32_t r = 0; r < n_ranges; ++r) {
        int32_t s = std::max(0, starts[r]);
        int32_t e = std::min(N, ends[r]);
        if (e <= s) continue;
        const float* vec = vectors + static_cast<int64_t>(s) * stride;
        for (int32_t id = s; id < e; ++id, vec += stride) {
            float sc = UseNeon ? dot_f32_neon(vec, query, d) : dot_f32_scalar(vec, query, d);
            if (!heap.full() || sc > heap.min_score()) {
                heap.push(sc, id);
            }
        }
        evals += static_cast<int64_t>(e - s);
    }
    heap.sort_descending();
    int32_t n_out = static_cast<int32_t>(heap.data.size());
    for (int32_t i = 0; i < n_out; ++i) {
        out_ids[i] = heap.data[i].id;
        out_scores[i] = heap.data[i].score;
    }
    return evals;
}

template <bool UseNeon>
static inline int64_t scan_zorder_sq8_impl(
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
    AuditTopKHeap<int32_t> pre_heap(rk);
    const int64_t stride = static_cast<int64_t>(d);
    int64_t evals = 0;

    for (int32_t r = 0; r < n_ranges; ++r) {
        int32_t s = std::max(0, starts[r]);
        int32_t e = std::min(N, ends[r]);
        if (e <= s) continue;
        const int8_t* vec = sq8_vectors + static_cast<int64_t>(s) * stride;
        for (int32_t id = s; id < e; ++id, vec += stride) {
            int32_t sc = UseNeon ? dot_sq8_neon(vec, q_sq8, d) : dot_sq8_scalar(vec, q_sq8, d);
            if (!pre_heap.full() || sc > pre_heap.min_score()) {
                pre_heap.push(sc, id);
            }
        }
        evals += static_cast<int64_t>(e - s);
    }
    if (pre_heap.data.empty()) return evals;

    AuditTopKHeap<float> exact_heap(k);
    for (const auto& entry : pre_heap.data) {
        const float* vec = fp32_vectors + static_cast<int64_t>(entry.id) * stride;
        float sc = UseNeon ? dot_f32_neon(vec, q_fp32, d) : dot_f32_scalar(vec, q_fp32, d);
        exact_heap.push(sc, entry.id);
    }
    exact_heap.sort_descending();
    int32_t n_out = static_cast<int32_t>(exact_heap.data.size());
    for (int32_t i = 0; i < n_out; ++i) {
        out_ids[i] = exact_heap.data[i].id;
        out_scores[i] = exact_heap.data[i].score;
    }
    return evals;
}

}  // namespace

extern "C" {

int64_t audit_scan_scattered_f32_scalar(
    const float* vectors, int32_t N, int32_t d, const float* query,
    const int32_t* ids, int32_t n_cand, int32_t k, int32_t* out_ids, float* out_scores
) {
    return scan_scattered_f32_impl<false>(vectors, N, d, query, ids, n_cand, k, out_ids, out_scores);
}

int64_t audit_scan_scattered_f32_neon(
    const float* vectors, int32_t N, int32_t d, const float* query,
    const int32_t* ids, int32_t n_cand, int32_t k, int32_t* out_ids, float* out_scores
) {
    return scan_scattered_f32_impl<true>(vectors, N, d, query, ids, n_cand, k, out_ids, out_scores);
}

int64_t audit_scan_zorder_f32_scalar(
    const float* vectors, int32_t N, int32_t d, const float* query,
    const int32_t* starts, const int32_t* ends, int32_t n_ranges, int32_t k,
    int32_t* out_ids, float* out_scores
) {
    return scan_zorder_f32_impl<false>(vectors, N, d, query, starts, ends, n_ranges, k, out_ids, out_scores);
}

int64_t audit_scan_zorder_f32_neon(
    const float* vectors, int32_t N, int32_t d, const float* query,
    const int32_t* starts, const int32_t* ends, int32_t n_ranges, int32_t k,
    int32_t* out_ids, float* out_scores
) {
    return scan_zorder_f32_impl<true>(vectors, N, d, query, starts, ends, n_ranges, k, out_ids, out_scores);
}

int64_t audit_scan_zorder_sq8_scalar(
    const int8_t* sq8_vectors, const float* fp32_vectors, int32_t N, int32_t d,
    const int8_t* q_sq8, const float* q_fp32, const int32_t* starts, const int32_t* ends,
    int32_t n_ranges, int32_t k, int32_t rerank_k, int32_t* out_ids, float* out_scores
) {
    return scan_zorder_sq8_impl<false>(
        sq8_vectors, fp32_vectors, N, d, q_sq8, q_fp32, starts, ends, n_ranges, k, rerank_k, out_ids, out_scores
    );
}

int64_t audit_scan_zorder_sq8_neon(
    const int8_t* sq8_vectors, const float* fp32_vectors, int32_t N, int32_t d,
    const int8_t* q_sq8, const float* q_fp32, const int32_t* starts, const int32_t* ends,
    int32_t n_ranges, int32_t k, int32_t rerank_k, int32_t* out_ids, float* out_scores
) {
    return scan_zorder_sq8_impl<true>(
        sq8_vectors, fp32_vectors, N, d, q_sq8, q_fp32, starts, ends, n_ranges, k, rerank_k, out_ids, out_scores
    );
}

uint64_t audit_flush_llc_cache(uint8_t* thrash_buf, int64_t n_bytes) {
    volatile uint8_t* vb = thrash_buf;
    uint64_t acc = 0;
    for (int64_t i = 0; i < n_bytes; i += 64) {
        uint8_t v = static_cast<uint8_t>(vb[i] + 1U);
        vb[i] = v;
        acc += v;
    }
    return acc;
}

}  // extern "C"
