import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import type { SkeletonBatch, NeuronIndexRow } from "../api";

type Props = {
  batch: SkeletonBatch | null;
  index: NeuronIndexRow[];
  selectedId: number | null;
  upstream: Set<number>;
  downstream: Set<number>;
  isolated: boolean;
  showSomas?: boolean;
  showLinks?: boolean;
  focusNonce?: number;
  onSelect?: (id: number) => void;
};

function colorFor(id: number, selectedId: number | null, upstream: Set<number>, downstream: Set<number>, dim: boolean) {
  if (selectedId === id) return new THREE.Color("#ffe9a8");
  if (upstream.has(id)) return new THREE.Color("#7ad0ff");
  if (downstream.has(id)) return new THREE.Color("#ffb06a");
  if (dim) return new THREE.Color("#1e332c");
  return new THREE.Color("#4fd4b0");
}

function boundsOf(segments: number[]): THREE.Box3 | null {
  if (!segments.length) return null;
  const box = new THREE.Box3();
  const v = new THREE.Vector3();
  for (let i = 0; i + 2 < segments.length; i += 3) {
    box.expandByPoint(v.set(segments[i], segments[i + 1], segments[i + 2]));
  }
  return box.isEmpty() ? null : box;
}

function makeLineGeom(positions: number[], colors?: number[]) {
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  if (colors) g.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  g.computeBoundingSphere();
  g.computeBoundingBox();
  return g;
}

/** Frames once on nonce change, then releases so OrbitControls work. */
function RigCamera({
  target,
  distance,
  nonce,
}: {
  target: THREE.Vector3;
  distance: number;
  nonce: number;
}) {
  const { camera, controls } = useThree();
  const goal = useRef(target.clone());
  const dist = useRef(distance);
  const armed = useRef(false);
  const until = useRef(0);

  useEffect(() => {
    goal.current.copy(target);
    dist.current = Math.max(distance, 1200);
    armed.current = true;
    until.current = performance.now() + 850;
  }, [target.x, target.y, target.z, distance, nonce]);

  useFrame((_, dt) => {
    if (!armed.current || !controls) return;
    const ctrl = controls as unknown as { target: THREE.Vector3; update: () => void; enabled: boolean };
    const k = Math.min(1, dt * 5.5);
    goal.current.lerp(target, k);
    ctrl.target.lerp(goal.current, k);
    dist.current = THREE.MathUtils.lerp(dist.current, distance, k);
    const offset = new THREE.Vector3(0.9, 0.5, 1.15).normalize().multiplyScalar(dist.current);
    camera.position.lerp(goal.current.clone().add(offset), k);
    ctrl.update();
    const close =
      camera.position.distanceTo(goal.current.clone().add(offset)) < Math.max(80, distance * 0.02) &&
      ctrl.target.distanceTo(goal.current) < 40;
    if (performance.now() > until.current || close) {
      armed.current = false;
    }
  });
  return null;
}

function Scene({
  batch,
  index,
  selectedId,
  upstream,
  downstream,
  isolated,
  showSomas,
  showLinks,
  focusNonce = 0,
  onSelect,
}: Props) {
  const worldBox = useMemo(() => {
    const box = new THREE.Box3();
    const v = new THREE.Vector3();
    for (const n of batch?.neurons || []) {
      const s = n.line_segments;
      const step = Math.max(3, Math.floor(s.length / 400) * 3);
      for (let i = 0; i + 2 < s.length; i += step) {
        box.expandByPoint(v.set(s[i], s[i + 1], s[i + 2]));
      }
    }
    return box.isEmpty() ? null : box;
  }, [batch]);

  const world = useMemo(
    () => (worldBox ? worldBox.getCenter(new THREE.Vector3()) : new THREE.Vector3()),
    [worldBox],
  );

  const overviewSpan = useMemo(() => {
    if (!worldBox) return 40000;
    return Math.max(8000, worldBox.getSize(new THREE.Vector3()).length());
  }, [worldBox]);

  const contextGeom = useMemo(() => {
    if (!batch?.neurons.length) return null;
    const pos: number[] = [];
    const col: number[] = [];
    const dim = selectedId != null && isolated;
    for (const n of batch.neurons) {
      const id = n.source_id;
      if (selectedId === id) continue;
      const related = upstream.has(id) || downstream.has(id);
      if (isolated && selectedId != null && !related) continue;
      const c = colorFor(id, selectedId, upstream, downstream, Boolean(dim && !related));
      const s = n.line_segments;
      const boost = related ? 1 : dim ? 0.28 : 0.88;
      for (let i = 0; i + 5 < s.length; i += 6) {
        pos.push(s[i], s[i + 1], s[i + 2], s[i + 3], s[i + 4], s[i + 5]);
        col.push(c.r * boost, c.g * boost, c.b * boost, c.r * boost, c.g * boost, c.b * boost);
      }
    }
    return pos.length ? makeLineGeom(pos, col) : null;
  }, [batch, selectedId, upstream, downstream, isolated]);

  const selected = useMemo(() => batch?.neurons.find((n) => n.source_id === selectedId) || null, [batch, selectedId]);
  const selectedGeom = useMemo(() => {
    if (!selected?.line_segments.length) return null;
    return makeLineGeom(selected.line_segments);
  }, [selected]);

  const meta = useMemo(
    () => (selectedId == null ? null : index.find((n) => n.source_id === selectedId) || null),
    [index, selectedId],
  );

  const focus = useMemo(() => {
    if (selected?.line_segments.length) {
      const box = boundsOf(selected.line_segments);
      if (box) {
        const c = box.getCenter(new THREE.Vector3()).sub(world);
        const span = box.getSize(new THREE.Vector3()).length();
        return { target: c, distance: Math.max(2200, Math.min(42000, span * 2.3)) };
      }
    }
    if (meta?.soma_x != null) {
      return {
        target: new THREE.Vector3(meta.soma_x - world.x, meta.soma_y! - world.y, meta.soma_z! - world.z),
        distance: 9000,
      };
    }
    return { target: new THREE.Vector3(0, 0, 0), distance: Math.max(12000, overviewSpan * 1.35) };
  }, [selected, meta, world, overviewSpan]);

  const pickNearest = (point: THREE.Vector3) => {
    let best: number | null = null;
    let bestD = Infinity;
    const worldPoint = point.clone().add(world);
    for (const n of index) {
      if (n.soma_x == null) continue;
      const d =
        (n.soma_x - worldPoint.x) ** 2 + (n.soma_y! - worldPoint.y) ** 2 + (n.soma_z! - worldPoint.z) ** 2;
      if (d < bestD) {
        bestD = d;
        best = n.source_id;
      }
    }
    for (const n of batch?.neurons || []) {
      const s = n.line_segments;
      if (s.length < 3) continue;
      const d = (s[0] - worldPoint.x) ** 2 + (s[1] - worldPoint.y) ** 2 + (s[2] - worldPoint.z) ** 2;
      if (d < bestD) {
        bestD = d;
        best = n.source_id;
      }
    }
    if (best != null && bestD < 2.5e9) onSelect?.(best);
  };

  const somas = useMemo(() => {
    if (!showSomas) return [] as NeuronIndexRow[];
    return index.filter((n) => n.soma_x != null).slice(0, 600);
  }, [index, showSomas]);

  const links = useMemo(() => {
    if (!showLinks || selectedId == null || !meta?.soma_x) return null;
    const byId = new Map(index.map((n) => [n.source_id, n]));
    const pos: number[] = [];
    const col: number[] = [];
    const add = (id: number, color: string) => {
      const n = byId.get(id);
      if (!n?.soma_x || !meta?.soma_x) return;
      const c = new THREE.Color(color);
      pos.push(meta.soma_x, meta.soma_y!, meta.soma_z!);
      pos.push(n.soma_x, n.soma_y!, n.soma_z!);
      col.push(c.r, c.g, c.b, c.r, c.g, c.b);
    };
    upstream.forEach((id) => add(id, "#7ad0ff"));
    downstream.forEach((id) => add(id, "#ffb06a"));
    return pos.length ? makeLineGeom(pos, col) : null;
  }, [showLinks, selectedId, meta, index, upstream, downstream]);

  const frameNonce = focusNonce * 1_000_000 + (selectedId ?? 0) + (batch?.count ?? 0);

  return (
    <>
      <group
        position={[-world.x, -world.y, -world.z]}
        onClick={(e: ThreeEvent<MouseEvent>) => {
          e.stopPropagation();
          pickNearest(e.point);
        }}
      >
        {contextGeom && (
          <lineSegments geometry={contextGeom} frustumCulled={false}>
            <lineBasicMaterial vertexColors transparent opacity={0.92} depthWrite={false} />
          </lineSegments>
        )}
        {selectedGeom && (
          <lineSegments geometry={selectedGeom} frustumCulled={false}>
            <lineBasicMaterial color="#ffe9a8" transparent opacity={1} depthWrite={false} />
          </lineSegments>
        )}
        {links && (
          <lineSegments geometry={links} frustumCulled={false}>
            <lineBasicMaterial vertexColors transparent opacity={0.45} depthWrite={false} />
          </lineSegments>
        )}
        {somas.map((n) => {
          const id = n.source_id;
          if (isolated && selectedId != null && id !== selectedId && !upstream.has(id) && !downstream.has(id)) {
            return null;
          }
          const isSel = selectedId === id;
          const related = upstream.has(id) || downstream.has(id);
          const c = colorFor(id, selectedId, upstream, downstream, false);
          return (
            <mesh
              key={id}
              position={[n.soma_x!, n.soma_y!, n.soma_z!]}
              onClick={(e) => {
                e.stopPropagation();
                onSelect?.(id);
              }}
            >
              <sphereGeometry args={[isSel ? 420 : related ? 240 : 160, 10, 10]} />
              <meshBasicMaterial color={c} transparent opacity={isSel ? 0.95 : related ? 0.75 : 0.5} depthWrite={false} />
            </mesh>
          );
        })}
      </group>
      <RigCamera target={focus.target} distance={focus.distance} nonce={frameNonce} />
    </>
  );
}

export function Viewer3D(props: Props) {
  return (
    <Canvas
      className="viewer-canvas"
      style={{ width: "100%", height: "100%", display: "block" }}
      camera={{ position: [18000, 12000, 22000], near: 1, far: 5e6, fov: 42 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
      resize={{ scroll: false, debounce: { scroll: 50, resize: 0 } }}
    >
      <color attach="background" args={["#08140f"]} />
      <fog attach="fog" args={["#08140f", 70000, 190000]} />
      <ambientLight intensity={0.7} />
      <directionalLight position={[2, 3, 1]} intensity={0.8} />
      <Scene {...props} />
      <OrbitControls makeDefault enableDamping dampingFactor={0.08} minDistance={400} maxDistance={4e5} />
    </Canvas>
  );
}
