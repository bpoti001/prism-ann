"""
Real external engine lifecycle managers for Prism-ANN v2 (ADR-0004).
====================================================================
Manages native Homebrew SpiceDB (gRPC) and native PostgreSQL 17 + pgvector 0.8.7
with guaranteed clean teardown in context-manager __exit__ / finally blocks.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import time
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from authzed.api.v1 import (
    Consistency,
    DeleteRelationshipsRequest,
    InsecureClient,
    LookupResourcesRequest,
    ObjectReference,
    ReadRelationshipsRequest,
    Relationship,
    RelationshipFilter,
    RelationshipUpdate,
    SubjectFilter,
    SubjectReference,
    WriteRelationshipsRequest,
    WriteSchemaRequest,
)

SPICEDB_BIN = "/opt/homebrew/bin/spicedb"
PG_BIN_DIR = "/opt/homebrew/opt/postgresql@17/bin"

ZANZIBAR_SCHEMA = """
definition user {}

definition container {
    relation parent: container
    relation viewer: user
    relation ethical_wall_deny: user
    permission denied = ethical_wall_deny + parent->denied
    permission view = (viewer + parent->view) - denied
}

definition document {
    relation parent: container
    relation viewer: user
    relation ethical_wall_deny: user
    permission denied = ethical_wall_deny + parent->denied
    permission view = (viewer + parent->view) - denied
}
"""


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _rel(rt: str, rid: str, reln: str, st: str, sid: str) -> Relationship:
    return Relationship(
        resource=ObjectReference(object_type=rt, object_id=rid),
        relation=reln,
        subject=SubjectReference(object=ObjectReference(object_type=st, object_id=sid)),
    )


def _node_type(node_id: str) -> str:
    return "document" if node_id.startswith("doc_") else "container"


class SpiceDBService:
    """Native local SpiceDB gRPC instance (in-memory datastore) with clean teardown."""

    def __init__(self, key: str = "devkey"):
        self.key = key
        self.port = _free_port()
        self.proc: Optional[subprocess.Popen] = None
        self.client: Optional[InsecureClient] = None
        self.last_zed_token = None
        self._stderr_file = None
        self._stderr_path: Optional[str] = None

    def __enter__(self) -> "SpiceDBService":
        fd, self._stderr_path = tempfile.mkstemp(prefix="prism_v2_spicedb_", suffix=".log")
        self._stderr_file = os.fdopen(fd, "w+b")
        self.proc = subprocess.Popen(
            [
                SPICEDB_BIN,
                "serve",
                "--grpc-preshared-key",
                self.key,
                "--datastore-engine",
                "memory",
                "--grpc-addr",
                f"127.0.0.1:{self.port}",
                "--http-enabled=false",
                "--metrics-enabled=false",
                "--dispatch-cluster-enabled=false",
                "--log-level=error",
            ],
            stdout=subprocess.DEVNULL,
            stderr=self._stderr_file,
        )
        deadline = time.perf_counter() + 15.0
        while time.perf_counter() < deadline:
            if self.proc.poll() is not None:
                self._stderr_file.flush()
                self._stderr_file.seek(0)
                err = self._stderr_file.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"SpiceDB exited prematurely: {err}")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            self.close()
            raise RuntimeError("SpiceDB failed to listen on gRPC port within 15s")

        self.client = InsecureClient(f"127.0.0.1:{self.port}", self.key)
        self.client.WriteSchema(WriteSchemaRequest(schema=ZANZIBAR_SCHEMA))
        return self

    def close(self) -> None:
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                    self.proc.wait(timeout=3)
                except Exception:
                    pass
            finally:
                self.proc = None
        if self._stderr_file is not None:
            try:
                self._stderr_file.close()
            except Exception:
                pass
            self._stderr_file = None
        if self._stderr_path is not None:
            try:
                os.unlink(self._stderr_path)
            except OSError:
                pass
            self._stderr_path = None
        self.client = None

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _write_updates(self, updates: List[RelationshipUpdate], batch_size: int = 500) -> object:
        assert self.client is not None
        zt = self.last_zed_token
        for i in range(0, len(updates), batch_size):
            resp = self.client.WriteRelationships(
                WriteRelationshipsRequest(updates=updates[i : i + batch_size])
            )
            zt = resp.written_at
        self.last_zed_token = zt
        return zt

    def load_hierarchy(self, auth_graph) -> object:
        """Writes all parent hierarchy edges from ZanzibarAuthGraph into SpiceDB."""
        updates: List[RelationshipUpdate] = []
        for parent_id, children in auth_graph.children.items():
            p_type = _node_type(parent_id)
            for child_id in children:
                c_type = _node_type(child_id)
                updates.append(
                    RelationshipUpdate(
                        operation=RelationshipUpdate.OPERATION_TOUCH,
                        relationship=_rel(c_type, child_id, "parent", p_type, parent_id),
                    )
                )
        return self._write_updates(updates)

    def write_principal_policy(
        self, principal_id: str, grants: Iterable[str], denies: Iterable[str]
    ) -> object:
        updates: List[RelationshipUpdate] = []
        for g in grants:
            updates.append(
                RelationshipUpdate(
                    operation=RelationshipUpdate.OPERATION_TOUCH,
                    relationship=_rel(_node_type(g), g, "viewer", "user", principal_id),
                )
            )
        for d in denies:
            updates.append(
                RelationshipUpdate(
                    operation=RelationshipUpdate.OPERATION_TOUCH,
                    relationship=_rel(_node_type(d), d, "ethical_wall_deny", "user", principal_id),
                )
            )
        if not updates:
            return self.last_zed_token
        return self._write_updates(updates)

    def lookup_resources_docs(self, principal_id: str, zed_token=None) -> Set[str]:
        """Streams all authorized leaf documents from real SpiceDB LookupResources gRPC."""
        assert self.client is not None
        zt = zed_token or self.last_zed_token
        consistency = (
            Consistency(at_least_as_fresh=zt) if zt is not None else Consistency(fully_consistent=True)
        )
        req = LookupResourcesRequest(
            consistency=consistency,
            resource_object_type="document",
            permission="view",
            subject=SubjectReference(object=ObjectReference(object_type="user", object_id=principal_id)),
        )
        return {resp.resource_object_id for resp in self.client.LookupResources(req)}

    def read_principal_grants_and_denies(
        self, principal_id: str, zed_token=None
    ) -> Tuple[Set[str], Set[str]]:
        """Reads a principal's direct grant and deny tuples live from SpiceDB via ReadRelationships."""
        assert self.client is not None
        zt = zed_token or self.last_zed_token
        consistency = (
            Consistency(at_least_as_fresh=zt) if zt is not None else Consistency(fully_consistent=True)
        )
        subj_filter = SubjectFilter(subject_type="user", optional_subject_id=principal_id)
        grants: Set[str] = set()
        denies: Set[str] = set()
        for rtype in ("container", "document"):
            for reln, target in (("viewer", grants), ("ethical_wall_deny", denies)):
                req = ReadRelationshipsRequest(
                    consistency=consistency,
                    relationship_filter=RelationshipFilter(
                        resource_type=rtype,
                        optional_relation=reln,
                        optional_subject_filter=subj_filter,
                    ),
                )
                for resp in self.client.ReadRelationships(req):
                    target.add(resp.relationship.resource.object_id)
        return grants, denies

    def delete_parent_edge(self, parent_id: str, child_id: str) -> object:
        """Real SpiceDB DeleteRelationships for one hierarchy edge."""
        assert self.client is not None
        resp = self.client.DeleteRelationships(
            DeleteRelationshipsRequest(
                relationship_filter=RelationshipFilter(
                    resource_type=_node_type(child_id),
                    optional_resource_id=child_id,
                    optional_relation="parent",
                    optional_subject_filter=SubjectFilter(
                        subject_type=_node_type(parent_id),
                        optional_subject_id=parent_id,
                    ),
                )
            )
        )
        self.last_zed_token = resp.deleted_at
        return resp.deleted_at

    def restore_parent_edge(self, parent_id: str, child_id: str) -> object:
        return self._write_updates(
            [
                RelationshipUpdate(
                    operation=RelationshipUpdate.OPERATION_TOUCH,
                    relationship=_rel(
                        _node_type(child_id), child_id, "parent", _node_type(parent_id), parent_id
                    ),
                )
            ]
        )


class SpiceDBPostgresService(SpiceDBService):
    """
    Native local SpiceDB gRPC instance backed by a real persistent PostgreSQL 17
    datastore (`--datastore-engine postgres`, ADR-0005 / PROTOCOL_v3).
    Runs `spicedb migrate head` before serving and tears down both daemons cleanly.
    """

    def __init__(self, key: str = "devkey"):
        super().__init__(key=key)
        self.pg_port = _free_port()
        self.pg_dir = tempfile.mkdtemp(prefix="prism_v3_spicedb_pg_")
        self.pg_started = False
        self.conn_uri = (
            f"postgres://postgres@127.0.0.1:{self.pg_port}/spicedb_store?sslmode=disable"
        )

    def __enter__(self) -> "SpiceDBPostgresService":
        try:
            subprocess.run(
                [
                    f"{PG_BIN_DIR}/initdb",
                    "-D",
                    self.pg_dir,
                    "-U",
                    "postgres",
                    "--auth=trust",
                    "--no-locale",
                    "-E",
                    "UTF8",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            opts = (
                f"-p {self.pg_port} -k {self.pg_dir} -c listen_addresses=127.0.0.1 "
                f"-c shared_buffers=256MB -c synchronous_commit=on"
            )
            subprocess.run(
                [
                    f"{PG_BIN_DIR}/pg_ctl",
                    "-D",
                    self.pg_dir,
                    "-l",
                    f"{self.pg_dir}/pg.log",
                    "-o",
                    opts,
                    "start",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.pg_started = True
            with psycopg.connect(
                host="127.0.0.1",
                port=self.pg_port,
                user="postgres",
                dbname="postgres",
                autocommit=True,
            ) as conn:
                conn.execute("CREATE DATABASE spicedb_store;")

            # Run real SpiceDB schema migration on PostgreSQL 17
            subprocess.run(
                [
                    SPICEDB_BIN,
                    "migrate",
                    "head",
                    "--datastore-engine",
                    "postgres",
                    "--datastore-conn-uri",
                    self.conn_uri,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            fd, self._stderr_path = tempfile.mkstemp(prefix="prism_v3_spicedb_pg_", suffix=".log")
            self._stderr_file = os.fdopen(fd, "w+b")
            self.proc = subprocess.Popen(
                [
                    SPICEDB_BIN,
                    "serve",
                    "--grpc-preshared-key",
                    self.key,
                    "--datastore-engine",
                    "postgres",
                    "--datastore-conn-uri",
                    self.conn_uri,
                    "--grpc-addr",
                    f"127.0.0.1:{self.port}",
                    "--http-enabled=false",
                    "--metrics-enabled=false",
                    "--dispatch-cluster-enabled=false",
                    "--log-level=error",
                ],
                stdout=subprocess.DEVNULL,
                stderr=self._stderr_file,
            )
            deadline = time.perf_counter() + 20.0
            while time.perf_counter() < deadline:
                if self.proc.poll() is not None:
                    self._stderr_file.flush()
                    self._stderr_file.seek(0)
                    err = self._stderr_file.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"SpiceDB(postgres) exited prematurely: {err}")
                try:
                    with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                raise RuntimeError("SpiceDB(postgres) failed to listen on gRPC port within 20s")

            self.client = InsecureClient(f"127.0.0.1:{self.port}", self.key)
            self.client.WriteSchema(WriteSchemaRequest(schema=ZANZIBAR_SCHEMA))
            return self
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        super().close()
        if self.pg_started:
            try:
                subprocess.run(
                    [f"{PG_BIN_DIR}/pg_ctl", "-D", self.pg_dir, "-m", "immediate", "stop"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
            except Exception:
                pass
            self.pg_started = False
        shutil.rmtree(self.pg_dir, ignore_errors=True)


class PostgresPgvectorService:
    """Native local PostgreSQL 17 + pgvector 0.8.7 instance with clean teardown."""

    def __init__(self, shared_buffers: str = "1GB", maintenance_work_mem: str = "2GB"):
        self.port = _free_port()
        self.pg_dir = tempfile.mkdtemp(prefix="prism_v2_pg_")
        self.shared_buffers = shared_buffers
        self.maintenance_work_mem = maintenance_work_mem
        self.started = False
        self.conn: Optional[psycopg.Connection] = None

    def __enter__(self) -> "PostgresPgvectorService":
        subprocess.run(
            [
                f"{PG_BIN_DIR}/initdb",
                "-D",
                self.pg_dir,
                "-U",
                "postgres",
                "--auth=trust",
                "--no-locale",
                "-E",
                "UTF8",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        opts = (
            f"-p {self.port} -k {self.pg_dir} -c listen_addresses=127.0.0.1 "
            f"-c shared_buffers={self.shared_buffers} "
            f"-c maintenance_work_mem={self.maintenance_work_mem} "
            f"-c max_parallel_maintenance_workers=4 "
            f"-c synchronous_commit=on "
            f"-c checkpoint_timeout=30min "
            f"-c max_wal_size=4GB"
        )
        subprocess.run(
            [f"{PG_BIN_DIR}/pg_ctl", "-D", self.pg_dir, "-l", f"{self.pg_dir}/pg.log", "-o", opts, "start"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.started = True
        self.conn = psycopg.connect(
            host="127.0.0.1", port=self.port, user="postgres", dbname="postgres", autocommit=True
        )
        self.conn.execute("CREATE EXTENSION vector;")
        register_vector(self.conn)
        return self

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
        if self.started:
            try:
                subprocess.run(
                    [f"{PG_BIN_DIR}/pg_ctl", "-D", self.pg_dir, "-m", "immediate", "stop"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
            except Exception:
                pass
            self.started = False
        shutil.rmtree(self.pg_dir, ignore_errors=True)

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def load_vectors_table(
        self,
        table: str,
        X: np.ndarray,
        doc_int_ids: np.ndarray,
        folder_int_ids: np.ndarray,
        insert_order: Optional[np.ndarray] = None,
        m: int = 16,
        ef_construction: int = 64,
        build_hnsw: bool = True,
    ) -> float:
        """Bulk-loads vectors via COPY (binary/text fast path) and builds pgvector HNSW index."""
        assert self.conn is not None
        N, d = X.shape
        t0 = time.perf_counter()
        self.conn.execute(f"DROP TABLE IF EXISTS {table};")
        self.conn.execute(
            f"CREATE TABLE {table} ("
            f"id INT PRIMARY KEY, doc_id INT NOT NULL, folder_id INT NOT NULL, "
            f"acl_allowed BOOLEAN NOT NULL DEFAULT TRUE, vec vector({d}) NOT NULL);"
        )
        order = np.arange(N, dtype=np.int32) if insert_order is None else insert_order
        with self.conn.cursor() as cur:
            with cur.copy(f"COPY {table} (id, doc_id, folder_id, acl_allowed, vec) FROM STDIN") as cp:
                for i in order:
                    idx = int(i)
                    vec_str = "[" + ",".join(f"{v:.6g}" for v in X[idx].tolist()) + "]"
                    cp.write_row((idx, int(doc_int_ids[idx]), int(folder_int_ids[idx]), True, vec_str))
        if build_hnsw:
            self.conn.execute(
                f"CREATE INDEX {table}_vec_hnsw_idx ON {table} "
                f"USING hnsw (vec vector_ip_ops) WITH (m = {m}, ef_construction = {ef_construction});"
            )
            self.conn.execute(f"ANALYZE {table};")
        return time.perf_counter() - t0

    def configure_hnsw_session(self, ef_search: int = 64) -> None:
        assert self.conn is not None
        self.conn.execute(f"SET hnsw.ef_search = {int(ef_search)};")
        self.conn.execute("SET hnsw.iterative_scan = relaxed_order;")
        # Ensure planner uses the HNSW index rather than falling back to sequential scan
        self.conn.execute("SET enable_seqscan = off;")

    def verify_uses_hnsw_index(self, table: str, q_vec: np.ndarray, allowed_docs: List[int], k: int = 10) -> str:
        assert self.conn is not None
        rows = self.conn.execute(
            f"EXPLAIN SELECT id FROM {table} WHERE doc_id = ANY(%s) ORDER BY vec <#> %s LIMIT %s",
            (allowed_docs, q_vec, k),
        ).fetchall()
        plan = "\n".join(r[0] for r in rows)
        return plan

    def search_filtered(
        self, table: str, q_vec: np.ndarray, allowed_docs: List[int], k: int = 10
    ) -> List[int]:
        assert self.conn is not None
        rows = self.conn.execute(
            f"SELECT id FROM {table} WHERE doc_id = ANY(%s) ORDER BY vec <#> %s LIMIT %s",
            (allowed_docs, q_vec, k),
        ).fetchall()
        return [int(r[0]) for r in rows]

    def update_acl_for_folder(self, table: str, folder_id: int, allowed: bool) -> int:
        """Executes a real transactional PostgreSQL UPDATE on all chunks in folder_id."""
        assert self.conn is not None
        with self.conn.transaction():
            cur = self.conn.execute(
                f"UPDATE {table} SET acl_allowed = %s WHERE folder_id = %s",
                (bool(allowed), int(folder_id)),
            )
            return int(cur.rowcount)
