#!/usr/bin/env python3
"""
Blast Radius Live Safety Proof for Prism-ANN (verify_blast_radius_ubp.py)
=========================================================================
Proves the #1 safety invariant of Prism-ANN (`ADR-0001` / Theorem 1 & Corollary 1):
  Exact Set Equivalence & Zero Privilege Escalation under Subtractive (`but not` / DENY) DAGs:
    Union_{t in T_UBP^+(u)} B_t \\ Union_{z in T_UBP^-(u)} B_z == Union_{r in D_auth(u)} B_r
    -> 0 False Positives (Zero Data Leaks / Zero Privilege Escalation)
    -> 0 False Negatives (Zero Dropped Authorized Chunks)

Stress-tests `src/modules/prism_ann` across 250+ randomized adversarial Zanzibar hierarchies:
  1. Balanced hierarchies (L in [2..5], b in [2..8], k_0 in [1..5], m in [0..25])
  2. Adversarial boundary cases (root deny, leaf deny, grant==deny, sibling denies,
     overlapping nested ancestor/descendant denies, outside-cone denies, empty grants,
     all-children-denied collapse)
  3. Multi-parent / Diamond Zanzibar DAGs (shared documents & folders with cross-parent DENY)
  4. Dynamic post-revocation states (`remove_hierarchy_edge`, `revoke_access`, `ZedToken` monotonicity)
"""

from __future__ import annotations
import os
import sys
import random
from typing import Dict, List, Set, Tuple
import numpy as np

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.modules.prism_ann import (
    PrismANNIndex,
    ZanzibarAuthGraph,
    ZOrderedCorpus,
    resolve_ubp_tokens,
)


def build_corpus_for_graph(graph: ZanzibarAuthGraph, seed: int = 7) -> ZOrderedCorpus:
    rng = np.random.default_rng(seed)
    leaves = sorted(graph.leaf_documents)
    lineages: List[List[str]] = []
    magnets: List[str] = []
    for idx, leaf in enumerate(leaves):
        anc = graph.get_ancestor_lineage(leaf)
        for c in range(2):
            lineages.append(anc)
            magnets.append(f"mag_{(idx + c) % 8}")
    vecs = rng.standard_normal((len(lineages), 16), dtype=np.float32)
    return ZOrderedCorpus(vecs, lineages, magnets)


def assert_exact_equivalence(
    graph: ZanzibarAuthGraph,
    corpus: ZOrderedCorpus,
    principal: str,
    scenario_name: str,
    check_bound: bool = True,
) -> Tuple[int, int]:
    expected_leaves = graph.lookup_resources_leaf(principal)
    expected_ids = corpus.compile_acl_bitmap_naive_leaves(expected_leaves).to_id_set()

    ubp_res = graph.upward_boundary_prune(principal)
    tokens_pos, tokens_neg = resolve_ubp_tokens(graph, principal)
    assert tokens_pos == ubp_res.tokens_pos
    assert tokens_neg == ubp_res.tokens_neg

    actual_ids = corpus.compile_acl_bitmap_ubp(tokens_pos, tokens_neg).to_id_set()

    false_positives = actual_ids - expected_ids
    false_negatives = expected_ids - actual_ids
    if false_positives or false_negatives:
        raise AssertionError(
            f"[{scenario_name}] SAFETY INVARIANT VIOLATION! "
            f"FP (leaks)={len(false_positives)}, FN (dropped)={len(false_negatives)}, "
            f"tokens_pos={tokens_pos}, tokens_neg={tokens_neg}"
        )

    if check_bound and len(tokens_pos) > ubp_res.theoretical_upper_bound:
        raise AssertionError(
            f"[{scenario_name}] Theorem 1 bound exceeded: "
            f"|T_UBP^+|={len(tokens_pos)} > bound={ubp_res.theoretical_upper_bound}"
        )

    return len(tokens_pos), ubp_res.theoretical_upper_bound


def run_edge_case_suite() -> int:
    cases_tested = 0
    # 1. Balanced tree L=4, b=4 for exhaustive adversarial edge cases
    base_graph = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=4, depth=4)
    corpus = build_corpus_for_graph(base_graph, seed=11)
    leaves = sorted(base_graph.leaf_documents)
    l1_nodes = [n for n in sorted(base_graph.all_nodes) if base_graph.node_depth[n] == 1]
    l2_nodes = [n for n in sorted(base_graph.all_nodes) if base_graph.node_depth[n] == 2]
    l3_nodes = [n for n in sorted(base_graph.all_nodes) if base_graph.node_depth[n] == 3]

    # Case A: Root deny overrides root grant
    base_graph.grant_access("u_root_deny", "node_L0_0")
    base_graph.add_deny_exclusion("u_root_deny", "node_L0_0")
    assert_exact_equivalence(base_graph, corpus, "u_root_deny", "RootDenyOverridesRootGrant")
    cases_tested += 1

    # Case B: Ancestor deny overrides descendant grant
    base_graph.grant_access("u_anc_deny", l2_nodes[0])
    base_graph.add_deny_exclusion("u_anc_deny", "node_L0_0")
    assert_exact_equivalence(base_graph, corpus, "u_anc_deny", "AncestorDenyOverridesChildGrant")
    cases_tested += 1

    # Case C: Empty grants with multiple denies
    base_graph.add_deny_exclusion("u_empty", l1_nodes[0])
    base_graph.add_deny_exclusion("u_empty", leaves[0])
    assert_exact_equivalence(base_graph, corpus, "u_empty", "EmptyPositiveGrantsWithDenies")
    cases_tested += 1

    # Case D: Grant == Deny on interior node, plus sibling grant
    base_graph.grant_access("u_self_deny", l1_nodes[0])
    base_graph.grant_access("u_self_deny", l1_nodes[1])
    base_graph.add_deny_exclusion("u_self_deny", l1_nodes[0])
    assert_exact_equivalence(base_graph, corpus, "u_self_deny", "SelfDenyPlusSiblingGrant")
    cases_tested += 1

    # Case E: Redundant nested positive grants + overlapping ancestor/descendant denies
    base_graph.grant_access("u_nested", "node_L0_0")
    base_graph.grant_access("u_nested", l1_nodes[0])
    base_graph.grant_access("u_nested", leaves[0])
    base_graph.add_deny_exclusion("u_nested", l1_nodes[0])
    base_graph.add_deny_exclusion("u_nested", l2_nodes[0])
    base_graph.add_deny_exclusion("u_nested", leaves[0])
    assert_exact_equivalence(base_graph, corpus, "u_nested", "NestedGrantsOverlappingDenies")
    cases_tested += 1

    # Case F: All children of a granted container individually denied
    parent_l3 = l3_nodes[2]
    base_graph.grant_access("u_all_kids_denied", parent_l3)
    for ch in base_graph.children[parent_l3]:
        base_graph.add_deny_exclusion("u_all_kids_denied", ch)
    assert_exact_equivalence(base_graph, corpus, "u_all_kids_denied", "AllChildrenDeniedCollapse")
    cases_tested += 1

    # Case G: Outside-cone deny (grant L1_0, deny under L1_3)
    base_graph.grant_access("u_outside", l1_nodes[0])
    base_graph.add_deny_exclusion("u_outside", l1_nodes[3])
    assert_exact_equivalence(base_graph, corpus, "u_outside", "OutsideConeDeny")
    cases_tested += 1

    # Case H: Dynamic revocation + re-check ZedToken monotonicity
    zed_before = base_graph.zed_token
    zed_after = base_graph.remove_hierarchy_edge("node_L0_0", l1_nodes[2])
    assert zed_after > zed_before
    assert_exact_equivalence(base_graph, corpus, "u_nested", "PostRevocationNestedUser")
    assert_exact_equivalence(base_graph, corpus, "u_outside", "PostRevocationOutsideUser")
    cases_tested += 2

    return cases_tested


def build_random_diamond_dag(rng: random.Random, num_l1: int = 4, num_l2: int = 8, num_leaves: int = 32) -> ZanzibarAuthGraph:
    """Constructs a multi-parent diamond Zanzibar DAG (shared folders and shared leaf docs)."""
    dag = ZanzibarAuthGraph(branching_factor=max(num_l1, num_l2, 4), depth=3)
    root = "org_0"
    dag.add_node(root, depth_level=0, is_leaf=False)

    l1_list = [f"lob_{i}" for i in range(num_l1)]
    for n in l1_list:
        dag.add_node(n, depth_level=1, is_leaf=False)
        dag.add_hierarchy_edge(root, n)

    l2_list = [f"dept_{i}" for i in range(num_l2)]
    for idx, n in enumerate(l2_list):
        dag.add_node(n, depth_level=2, is_leaf=False)
        # Attach to 1 or 2 L1 parents (diamond DAG)
        parents = rng.sample(l1_list, k=rng.choice([1, 2]))
        for p in parents:
            dag.add_hierarchy_edge(p, n)

    for idx in range(num_leaves):
        leaf = f"doc_{idx}"
        dag.add_node(leaf, depth_level=3, is_leaf=True)
        parents = rng.sample(l2_list, k=rng.choice([1, 2]))
        for p in parents:
            dag.add_hierarchy_edge(p, leaf)

    return dag


def run_randomized_fuzzer() -> Dict[str, int]:
    rng = random.Random(20261119)
    total_tree_trials = 0
    total_dag_trials = 0
    total_revocations = 0

    # 1. 150 Randomized Balanced Tree Scenarios across diverse (b, L, k0, m)
    configs = [(3, 4), (4, 4), (5, 3), (6, 3), (8, 3), (4, 5)]
    for trial in range(150):
        b, L = configs[trial % len(configs)]
        graph = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=b, depth=L)
        corpus = build_corpus_for_graph(graph, seed=1000 + trial)
        all_nodes = sorted(graph.all_nodes)
        non_root = [n for n in all_nodes if graph.node_depth[n] >= 1]

        principal = f"fuzz_tree_{trial}"
        k0 = rng.randint(1, 5)
        grant_pool = [n for n in all_nodes if graph.node_depth[n] <= L - 1]
        for g in rng.sample(grant_pool, k=min(k0, len(grant_pool))):
            graph.grant_access(principal, g)

        m_denies = rng.randint(0, min(20, len(non_root)))
        for d_node in rng.sample(non_root, k=m_denies):
            graph.add_deny_exclusion(principal, d_node)

        # In trees, enforce Theorem 1 bound with k_0 <= len(g0_pos)
        assert_exact_equivalence(graph, corpus, principal, f"TreeTrial_{trial}", check_bound=True)
        total_tree_trials += 1

        # Trigger dynamic edge revocation on every 3rd trial
        if trial % 3 == 0:
            victim = rng.choice(non_root)
            parent = next(iter(graph.parents[victim]))
            graph.remove_hierarchy_edge(parent, victim)
            assert_exact_equivalence(graph, corpus, principal, f"TreeTrial_{trial}_PostRevoke", check_bound=True)
            total_revocations += 1

    # 2. 100 Randomized Multi-Parent Diamond DAG Scenarios (with cross-parent DENY)
    for trial in range(100):
        dag = build_random_diamond_dag(rng, num_l1=4, num_l2=8, num_leaves=36)
        corpus = build_corpus_for_graph(dag, seed=5000 + trial)
        all_nodes = sorted(dag.all_nodes)

        principal = f"fuzz_dag_{trial}"
        k0 = rng.randint(1, 4)
        for g in rng.sample(all_nodes, k=k0):
            dag.grant_access(principal, g)

        m_denies = rng.randint(0, 8)
        for d_node in rng.sample(all_nodes, k=m_denies):
            dag.add_deny_exclusion(principal, d_node)

        # Note: in multi-parent DAGs, Theorem 1's tree bound k_0 + m*(b-1)*L does not apply directly
        # because diamond paths fan out across multiple parents, so we check exact set equivalence (0 FP / 0 FN).
        assert_exact_equivalence(dag, corpus, principal, f"DiamondDAG_{trial}", check_bound=False)
        total_dag_trials += 1

        if trial % 2 == 0:
            non_root = [n for n in all_nodes if dag.node_depth[n] >= 1]
            victim = rng.choice(non_root)
            parent = next(iter(dag.parents[victim]))
            dag.remove_hierarchy_edge(parent, victim)
            assert_exact_equivalence(dag, corpus, principal, f"DiamondDAG_{trial}_PostRevoke", check_bound=False)
            total_revocations += 1

    return {
        "tree_trials": total_tree_trials,
        "diamond_dag_trials": total_dag_trials,
        "dynamic_revocations": total_revocations,
    }


def run_end_to_end_downstream_search_proof() -> int:
    """
    Blast Radius Step 3+4 ("code three hops downstream"):
    Proves that `PrismANNIndex.search()` across Mode 1 (1-Hop HNSW), Mode 2 (H-HNSW + ACORN-GLS),
    Mode 3 (Z-Order Roaring-SIMD), and post-revocation NEVER surfaces any chunk whose leaf
    document is outside D_auth(u) or whose Meaning Magnet is outside concept_ids.
    """
    graph = ZanzibarAuthGraph.build_balanced_hierarchy(branching_factor=4, depth=3)
    leaves = sorted(graph.leaf_documents)
    rng = np.random.default_rng(909)
    lineages: List[List[str]] = []
    magnets: List[str] = []
    for leaf in leaves:
        anc = graph.get_ancestor_lineage(leaf)
        for c in range(8):
            lineages.append(anc)
            magnets.append(f"mag_{c % 4}")
    vecs = rng.standard_normal((len(lineages), 32), dtype=np.float32)
    prism = PrismANNIndex(graph, vecs, lineages, magnets, m_degree=12, m_bridge=4, ef_search=48, seed=42)

    scenarios = [
        ("u_mode1", ["node_L0_0"], [leaves[0], leaves[1]], None),
        ("u_mode2", ["node_L1_0", "node_L1_1"], ["node_L2_4", leaves[2]], {"mag_0", "mag_2"}),
        ("u_mode3", [leaves[10]], [], {"mag_1"}),
        ("u_revoked_all", ["node_L1_2"], ["node_L1_2"], None),
    ]
    checked = 0
    for pid, grants, denies, ont_filter in scenarios:
        for g in grants:
            graph.grant_access(pid, g)
        for d in denies:
            graph.add_deny_exclusion(pid, d)
        auth_leaves = graph.lookup_resources_leaf(pid)
        for q_idx in [0, 77, 250, 411]:
            res = prism.search(vecs[q_idx], principal_id=pid, concept_ids=ont_filter, k=10)
            for z_id in res.top_k_ids:
                leaf_doc = prism.z_corpus.leaf_doc_ids[z_id]
                mag_id = prism.z_corpus.meaning_magnet_ids[z_id]
                if leaf_doc not in auth_leaves:
                    raise AssertionError(
                        f"DOWNSTREAM SEARCH LEAK! principal={pid}, mode={res.execution_mode}, leaked leaf={leaf_doc}"
                    )
                if ont_filter is not None and mag_id not in ont_filter:
                    raise AssertionError(
                        f"ONTOLOGY LEAK! principal={pid}, mode={res.execution_mode}, leaked magnet={mag_id}"
                    )
            checked += 1

    # Revoke an entire L1 subtree dynamically and re-verify Mode 2 -> 0 leaks
    prism.revoke_hierarchy_edge("node_L0_0", "node_L1_0")
    auth_after = graph.lookup_resources_leaf("u_mode2")
    res_after = prism.search(vecs[5], principal_id="u_mode2", concept_ids={"mag_0"}, k=10)
    for z_id in res_after.top_k_ids:
        leaf_doc = prism.z_corpus.leaf_doc_ids[z_id]
        if leaf_doc not in auth_after:
            raise AssertionError(f"POST-REVOCATION LEAK in PrismANNIndex.search(): {leaf_doc}")
    checked += 1
    return checked


def main() -> int:
    print("==================================================================")
    print("  Blast Radius Live Proof: UBP Zero-Leakage & Set Equivalence     ")
    print("==================================================================")
    edge_cases = run_edge_case_suite()
    print(f"  [PASS] Adversarial Edge-Case Suite: {edge_cases} cases -> 0 FP, 0 FN")

    stats = run_randomized_fuzzer()
    downstream = run_end_to_end_downstream_search_proof()
    total = (
        edge_cases
        + stats["tree_trials"]
        + stats["diamond_dag_trials"]
        + stats["dynamic_revocations"]
        + downstream
    )
    print(f"  [PASS] Balanced Hierarchy Trees: {stats['tree_trials']} randomized trials -> 0 FP, 0 FN, 100% Theorem 1 bound satisfied")
    print(f"  [PASS] Multi-Parent Diamond DAGs: {stats['diamond_dag_trials']} randomized trials -> 0 FP, 0 FN")
    print(f"  [PASS] Dynamic Post-Revocation Checks: {stats['dynamic_revocations']} mutations -> 0 FP, 0 FN")
    print(f"  [PASS] Downstream PrismANNIndex.search() E2E (Modes 1/2/3 + Post-Revoke): {downstream} queries -> 0 leaks")
    print("------------------------------------------------------------------")
    print(f"  TOTAL ADVERSARIAL SCENARIOS PROVEN: {total} | FALSE POSITIVES: 0 | FALSE NEGATIVES: 0")
    print("==================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
