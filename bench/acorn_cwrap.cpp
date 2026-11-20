// Minimal C ABI wrapper around stanford-futuredata/ACORN (IndexACORNFlat).
// Keeps the upstream C++ implementation untouched while exposing build +
// per-query filtered search + exact distance-computation count (acorn_stats.n3)
// to Python via ctypes.

#include <cstdint>
#include <cstring>
#include <vector>

#include <faiss/IndexACORN.h>
#include <faiss/impl/ACORN.h>
#include <faiss/impl/IDSelector.h>

namespace {
struct FilterMapSelector final : faiss::IDSelector {
    const char* filter_map;
    explicit FilterMapSelector(const char* fm) : filter_map(fm) {}
    bool is_member(faiss::idx_t id) const final {
        return id >= 0 && filter_map[id] != 0;
    }
};
}  // namespace

struct AcornHandle {
    std::vector<int> metadata;
    faiss::IndexACORNFlat* index;
    int d;
    int M;
    int gamma;
    int M_beta;
};

extern "C" {

void* acorn_create(int d, int M, int gamma, int M_beta, int n_expected, int seed, int ef_construction) {
    auto* h = new AcornHandle();
    h->d = d;
    h->M = M;
    h->gamma = gamma;
    h->M_beta = M_beta;
    // ACORN-1 (gamma=1) is predicate-agnostic during construction, but
    // IndexACORNFlat requires a metadata array of size >= n_expected.
    h->metadata.assign(n_expected > 0 ? n_expected : 1, 0);
    // Use METRIC_L2 (upstream ACORN's default; mathematically identical to cosine/IP
    // on unit-normalized vectors since ||u-v||^2 = 2 - 2<u,v>, while avoiding
    // negative-distance artifacts in upstream ACORN::shrink_neighbor_list).
    h->index = new faiss::IndexACORNFlat(
        d, M, gamma, h->metadata, M_beta, faiss::METRIC_L2);
    h->index->acorn.rng = faiss::RandomGenerator(12345 + seed * 997);
    if (ef_construction > 0) {
        h->index->acorn.efConstruction = ef_construction;
    }
    return static_cast<void*>(h);
}

void acorn_add(void* ptr, int64_t n, const float* vectors) {
    auto* h = static_cast<AcornHandle*>(ptr);
    if (static_cast<int64_t>(h->metadata.size()) < h->index->ntotal + n) {
        h->metadata.resize(h->index->ntotal + n, 0);
        h->index->acorn.metadata = h->metadata.data();
    }
    h->index->add(static_cast<faiss::idx_t>(n), vectors);
}

int64_t acorn_search_one(
    void* ptr,
    const float* query,
    int k,
    int ef_search,
    char* filter_map,
    int64_t* out_ids,
    float* out_dists
) {
    auto* h = static_cast<AcornHandle*>(ptr);
    h->index->acorn.efSearch = ef_search;
    faiss::acorn_stats.reset();
    FilterMapSelector sel(filter_map);
    faiss::SearchParametersACORN params;
    params.efSearch = ef_search;
    params.sel = &sel;
    std::vector<faiss::idx_t> labels(k, -1);
    std::vector<float> dists(k, 0.0f);
    h->index->search(1, query, k, dists.data(), labels.data(), filter_map, &params);
    for (int i = 0; i < k; ++i) {
        out_ids[i] = static_cast<int64_t>(labels[i]);
        out_dists[i] = dists[i];
    }
    // Upstream ACORN.cpp accumulates all upper- and level-0 distance evaluations
    // in acorn_stats.n3 (plus 1 initial entry-point evaluation when entry_point != -1).
    int64_t ndis = static_cast<int64_t>(faiss::acorn_stats.n3);
    if (h->index->acorn.entry_point != -1) {
        ndis += 1;
    }
    return ndis;
}

void acorn_destroy(void* ptr) {
    auto* h = static_cast<AcornHandle*>(ptr);
    if (h) {
        delete h->index;
        delete h;
    }
}

}  // extern "C"
