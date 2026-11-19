"""
SpiceDB / Google Zanzibar Subtractive-Aware Upward Boundary Pruning (UBP)
=========================================================================
Governing ADR: ADR-0001 (docs/adr/0001-spicedb-subtractive-upward-boundary-pruning.md)
Mapped Theorems:
  - Theorem 1 (UBP Token Cardinality Bound & Exact Set Equivalence):
      |T_UBP^+(u)| <= k_0 + m * (b - 1) * L
      Union_{t in T_UBP^+(u)} B_t \\ Union_{z in T_UBP^-(u)} B_z == Union_{r in D_auth(u)} B_r
  - Corollary 1 (Zero-Write O(1) Document & Container Revocation)
"""

from __future__ import annotations
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple


@dataclass
class UBPResolutionResult:
    """Output of Subtractive-Aware Upward Boundary Pruning (P_UBP)."""
    principal_id: str
    tokens_pos: Set[str]
    tokens_neg: Set[str]
    k0_grants: int
    m_denies: int
    theoretical_upper_bound: int
    tainted_containers: Set[str]
    zed_token: int
    resolution_time_ms: float


class ZanzibarAuthGraph:
    """
    Hierarchical Google Zanzibar / SpiceDB ReBAC Authorization Graph
    G_auth = (U u G u R, E^+ u E^-).

    Models an organizational container hierarchy of depth L and branching factor b:
      level 0 (org) -> level 1 (lob) -> ... -> level L (leaf document r in R)
    Supports:
      - Positive grants E^+: (principal_id -> node_id)
      - Subtractive exclusions E^- ('but not' / ethical_wall_deny): (principal_id -> node_id)
      - O(1) structural edge mutations and revocations with ZedToken causal consistency.
    """

    def __init__(self, branching_factor: int = 8, depth: int = 4):
        self.b = branching_factor
        self.L = depth
        self.children: Dict[str, List[str]] = {}
        self.parents: Dict[str, Set[str]] = {}
        self.node_depth: Dict[str, int] = {}
        self.leaf_documents: Set[str] = set()
        self.all_nodes: Set[str] = set()

        # Principal permissions: E^+ (positive grants) and E^- (explicit DENY / 'but not' walls)
        self.positive_grants: Dict[str, Set[str]] = {}
        self.explicit_denies: Dict[str, Set[str]] = {}
        # Globally unlinked / superseded containers or documents (for zero-write revocation over immutable lineages)
        self.revoked_subtrees: Set[str] = set()

        # Causal consistency timestamp (SpiceDB ZedToken / Zanzibar Zookie)
        self.zed_token: int = 1

    @classmethod
    def build_balanced_hierarchy(cls, branching_factor: int = 8, depth: int = 4) -> "ZanzibarAuthGraph":
        """
        Builds a deterministic balanced organizational hierarchy tree of depth L and branching b.
        Root is 'node_L0_0' at depth 0; leaves at depth L are 'doc_L{L}_{idx}'.
        """
        graph = cls(branching_factor=branching_factor, depth=depth)
        root_id = "node_L0_0"
        graph.add_node(root_id, depth_level=0, is_leaf=(depth == 0))

        current_level_nodes = [root_id]
        for lvl in range(1, depth + 1):
            next_level_nodes = []
            is_leaf = (lvl == depth)
            prefix = "doc" if is_leaf else "node"
            counter = 0
            for parent_id in current_level_nodes:
                for _ in range(branching_factor):
                    child_id = f"{prefix}_L{lvl}_{counter}"
                    counter += 1
                    graph.add_node(child_id, depth_level=lvl, is_leaf=is_leaf)
                    graph.add_hierarchy_edge(parent_id, child_id)
                    next_level_nodes.append(child_id)
            current_level_nodes = next_level_nodes

        return graph

    def add_node(self, node_id: str, depth_level: int, is_leaf: bool = False) -> None:
        self.all_nodes.add(node_id)
        self.node_depth[node_id] = depth_level
        if node_id not in self.children:
            self.children[node_id] = []
        if node_id not in self.parents:
            self.parents[node_id] = set()
        if is_leaf:
            self.leaf_documents.add(node_id)

    def add_hierarchy_edge(self, parent_id: str, child_id: str) -> None:
        if child_id not in self.children.get(parent_id, []):
            self.children.setdefault(parent_id, []).append(child_id)
        self.parents.setdefault(child_id, set()).add(parent_id)
        self.revoked_subtrees.discard(child_id)
        self.zed_token += 1

    def remove_hierarchy_edge(self, parent_id: str, child_id: str) -> int:
        """
        O(1) structural edge deletion in SpiceDB (Corollary 1: Zero-Write Revocation).
        Because vector chunks carry immutable ingest-time ancestor paths Anc(v_i),
        marking child_id as an unlinked boundary automatically prunes child_id via UBP
        without mutating a single vector record.
        """
        self.revoked_subtrees.add(child_id)
        self.zed_token += 1
        return self.zed_token

    def grant_access(self, principal_id: str, node_id: str) -> int:
        """Add positive relation tuple <node_id>#viewer@<principal_id> in E^+."""
        self.positive_grants.setdefault(principal_id, set()).add(node_id)
        self.zed_token += 1
        return self.zed_token

    def revoke_access(self, principal_id: str, node_id: str) -> int:
        """
        O(1) zero-write revocation of a grant tuple in SpiceDB (Corollary 1).
        """
        if principal_id in self.positive_grants:
            self.positive_grants[principal_id].discard(node_id)
        self.zed_token += 1
        return self.zed_token

    def add_deny_exclusion(self, principal_id: str, node_id: str) -> int:
        """
        Add subtractive exclusion tuple <node_id>#ethical_wall_deny@<principal_id> in E^-.
        """
        self.explicit_denies.setdefault(principal_id, set()).add(node_id)
        self.zed_token += 1
        return self.zed_token

    def get_ancestor_lineage(self, node_id: str) -> List[str]:
        """
        Returns the immutable structural container lineage Anc(v_i) from root to node_id.
        """
        lineage = []
        visited = set()
        stack = [node_id]
        while stack:
            curr = stack.pop()
            if curr not in visited:
                visited.add(curr)
                lineage.append(curr)
                for p in self.parents.get(curr, ()):
                    if p not in visited:
                        stack.append(p)
        lineage.sort(key=lambda x: (self.node_depth.get(x, 0), x == node_id, x))
        return lineage

    def get_strict_ancestors(self, node_id: str) -> Set[str]:
        """Returns all strict ancestors of node_id (excluding node_id itself)."""
        anc = set(self.get_ancestor_lineage(node_id))
        anc.discard(node_id)
        return anc

    def get_descendants(self, root_nodes: Set[str]) -> Set[str]:
        """Returns all descendants (including root_nodes themselves) reachable via hierarchy edges."""
        desc: Set[str] = set()
        stack = list(root_nodes)
        while stack:
            curr = stack.pop()
            if curr not in desc:
                desc.add(curr)
                for ch in self.children.get(curr, ()):
                    if ch not in desc:
                        stack.append(ch)
        return desc

    def lookup_resources_leaf(self, principal_id: str) -> Set[str]:
        """
        Baseline B2: Naive SpiceDB `LookupResources` exhaustive leaf expansion.
        Traverses all descendants of G_0^+(u), excluding any subtree rooted at V^-(u),
        and emits every authorized leaf document r in D_auth(u).
        Complexity: Theta(b^L) leaf tokens.
        """
        g0_pos = self.positive_grants.get(principal_id, set())
        v_neg = set(self.explicit_denies.get(principal_id, set())) | self.revoked_subtrees

        denied_closure = self.get_descendants(v_neg)
        authorized_leaves: Set[str] = set()

        stack = [g for g in g0_pos if g not in denied_closure]
        visited: Set[str] = set()
        while stack:
            curr = stack.pop()
            if curr in visited or curr in denied_closure:
                continue
            visited.add(curr)
            if curr in self.leaf_documents:
                authorized_leaves.add(curr)
            for ch in self.children.get(curr, ()):
                if ch not in visited and ch not in denied_closure:
                    stack.append(ch)

        return authorized_leaves

    def _minimal_positive_roots(self, g0_pos: Set[str]) -> Set[str]:
        """
        Filters redundant positive grants that are already descendants of a higher positive grant.
        """
        minimal: Set[str] = set()
        for g in g0_pos:
            strict_anc = self.get_strict_ancestors(g)
            if not (strict_anc & g0_pos):
                minimal.add(g)
        return minimal

    def upward_boundary_prune(self, principal_id: str) -> UBPResolutionResult:
        """
        Algorithm 1: Subtractive-Aware Upward Boundary Pruning (P_UBP).
        Governing ADR: ADR-0001 | Mapped Theorem: Theorem 1.

        Steps:
          1. Retrieve top-level positive grants G_0^+(u) and explicit denies V^-(u).
          2. Compute Tainted Ancestor Set:
               G_taint(u) = Union_{z in V^-(u)} (StrictAnc(z) n Desc(G_0^+(u)))
             Any container in G_taint(u) has at least one denied descendant and cannot
             be emitted as a monolithic prefix token without splitting.
          3. Perform top-down cut from G_0^+(u):
             - If x in V^-(u) (or Desc(V^-(u))): prune branch (emit to T_UBP^-(u)).
             - If x not in G_taint(u): HALT IMMEDIATELY and emit x into T_UBP^+(u).
             - If x in G_taint(u): recursively expand children(x).
        """
        t0 = time.perf_counter()
        raw_pos = self.positive_grants.get(principal_id, set())
        v_neg = set(self.explicit_denies.get(principal_id, set())) | self.revoked_subtrees

        g0_pos = self._minimal_positive_roots(raw_pos)
        k0 = max(1, len(g0_pos)) if raw_pos else 0
        m = len(v_neg)
        theoretical_bound = k0 + m * (self.b - 1) * self.L

        if not g0_pos:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return UBPResolutionResult(
                principal_id=principal_id,
                tokens_pos=set(),
                tokens_neg=v_neg,
                k0_grants=0,
                m_denies=m,
                theoretical_upper_bound=0,
                tainted_containers=set(),
                zed_token=self.zed_token,
                resolution_time_ms=elapsed_ms,
            )

        # Compute Tainted Ancestor Set G_taint(u) in O(m * L^2) upward walk without Theta(b^L) leaf expansion
        g_taint: Set[str] = set()
        for z in v_neg:
            z_anc = self.get_strict_ancestors(z)
            if (z_anc | {z}) & g0_pos:
                for anc in z_anc:
                    if (self.get_strict_ancestors(anc) | {anc}) & g0_pos:
                        g_taint.add(anc)

        tokens_pos: Set[str] = set()
        tokens_neg: Set[str] = set(v_neg)

        # Top-down boundary pruning traversal (halts at untainted or denied boundaries)
        queue = deque(g0_pos)
        visited: Set[str] = set()
        while queue:
            curr = queue.popleft()
            if curr in visited:
                continue
            visited.add(curr)

            if curr in v_neg or (self.get_strict_ancestors(curr) & v_neg):
                tokens_neg.add(curr)
                continue

            if curr not in g_taint:
                tokens_pos.add(curr)
            else:
                for ch in self.children.get(curr, ()):
                    if ch not in visited:
                        queue.append(ch)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return UBPResolutionResult(
            principal_id=principal_id,
            tokens_pos=tokens_pos,
            tokens_neg=tokens_neg,
            k0_grants=len(g0_pos),
            m_denies=m,
            theoretical_upper_bound=theoretical_bound,
            tainted_containers=g_taint,
            zed_token=self.zed_token,
            resolution_time_ms=elapsed_ms,
        )


def resolve_ubp_tokens(
    auth_graph: ZanzibarAuthGraph, principal_id: str
) -> Tuple[Set[str], Set[str]]:
    """
    Canonical Deep Module Seam (ADR-0001):
    Returns (T_UBP^+(u), T_UBP^-(u)) for a given principal_id in G_auth.
    """
    res = auth_graph.upward_boundary_prune(principal_id)
    return res.tokens_pos, res.tokens_neg
