import { Bounds, Grid, Html, Line, OrbitControls, PerspectiveCamera, Sphere, useGLTF } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import * as THREE from "three";
import type { Pose, SceneDeckItem, SceneInstrument, TwinBundle, WorkingVolume } from "./types";
import {
  currentMotionEvent,
  currentStepLabel,
  currentTargetLabel,
  getDeckYawRadians,
  getTotalDuration,
  isPointInsideVolume,
  phaseLabel,
  samplePlayback,
  toWorldPosition,
} from "./lib/playback";

const DEFAULT_BUNDLE_PATH = "/examples/asmi-panda-deck.json";

type ViewerToggles = {
  showGrid: boolean;
  showWorkingVolume: boolean;
  showGantryPath: boolean;
  showInstrumentOffsets: boolean;
};

function poseCenter(points: Pose[]): Pose {
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const zs = points.map((point) => point.z);
  return {
    x: (Math.min(...xs) + Math.max(...xs)) / 2,
    y: (Math.min(...ys) + Math.max(...ys)) / 2,
    z: (Math.min(...zs) + Math.max(...zs)) / 2,
  };
}

function poseSpread(points: Pose[], fallback: number): [number, number, number] {
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const zs = points.map((point) => point.z);
  return [
    Math.max(Math.max(...xs) - Math.min(...xs), fallback),
    Math.max(Math.max(...zs) - Math.min(...zs), fallback / 2),
    Math.max(Math.max(...ys) - Math.min(...ys), fallback),
  ];
}

function deckBoxPose(item: SceneDeckItem): { center: Pose; size: [number, number, number] } {
  const fallbackPoint = item.primary_position;
  const points = item.points.length > 0 ? item.points.map((point) => point.position) : [fallbackPoint];
  const center = poseCenter(points);
  const renderMeta = item.render_meta as {
    location?: Pose;
    labware_support_height_mm?: number;
    labware_seat_height_from_bottom_mm?: number;
  };
  let [length, height, width] = [
    item.dimensions.length_mm ?? poseSpread(points, 10)[0],
    item.dimensions.height_mm ?? 6,
    item.dimensions.width_mm ?? poseSpread(points, 10)[2],
  ];
  const topAnchored = item.render_kind === "well_plate" || item.render_kind === "tip_rack";
  const anchorLocation = renderMeta.location;
  const childPoints = item.points
    .filter((point) => point.id !== "location")
    .map((point) => point.position);
  const cornerAnchored =
    item.type === "tip_disposal" ||
    (item.type === "vial_holder" &&
      anchorLocation !== undefined &&
      points.some((point) => point.x > anchorLocation.x || point.y > anchorLocation.y));

  if ((item.type === "vial_holder" || item.type === "well_plate_holder") && anchorLocation) {
    height = Math.min(
      height,
      renderMeta.labware_seat_height_from_bottom_mm ?? renderMeta.labware_support_height_mm ?? 8,
    );
    const childCenter = childPoints.length > 0 ? poseCenter(childPoints) : center;
    return {
      center: {
        x: childCenter.x,
        y: childCenter.y,
        z: anchorLocation.z + height / 2,
      },
      size: [length, height, width],
    };
  }

  if (cornerAnchored && anchorLocation) {
    return {
      center: {
        x: anchorLocation.x + length / 2,
        y: anchorLocation.y + width / 2,
        z: anchorLocation.z + height / 2,
      },
      size: [length, height, width],
    };
  }

  return {
    center: {
      x: center.x,
      y: center.y,
      // Well/tip positions are contact/working points on the top surface, so the
      // mesh body should extend downward from them in user-space Z.
      z: topAnchored ? center.z + height / 2 : center.z,
    },
    size: [length, height, width],
  };
}

function WorkingVolumeFrame({ volume }: { volume: WorkingVolume }) {
  const center = {
    x: (volume.x_min + volume.x_max) / 2,
    y: (volume.y_min + volume.y_max) / 2,
    z: (volume.z_min + volume.z_max) / 2,
  };
  const size: [number, number, number] = [
    volume.x_max - volume.x_min,
    volume.z_max - volume.z_min,
    volume.y_max - volume.y_min,
  ];
  return (
    <mesh position={toWorldPosition(center)}>
      <boxGeometry args={size} />
      <meshBasicMaterial color="#1d1a15" transparent opacity={0.05} />
      <lineSegments>
        <edgesGeometry args={[new THREE.BoxGeometry(...size)]} />
        <lineBasicMaterial color="#2e5b51" transparent opacity={0.7} />
      </lineSegments>
    </mesh>
  );
}

function OriginMarker() {
  return (
    <group position={toWorldPosition({ x: 0, y: 0, z: 0 })}>
      <Sphere args={[2.2, 16, 16]}>
        <meshStandardMaterial color="#111111" />
      </Sphere>
      <Html
        position={[8, -8, 8]}
        style={{
          fontSize: "12px",
          fontWeight: 700,
          color: "#111111",
          background: "rgba(255,255,255,0.82)",
          padding: "3px 6px",
          borderRadius: "8px",
          whiteSpace: "nowrap",
        }}
      >
        0,0,0
      </Html>
    </group>
  );
}

function DeckItemMesh({ item }: { item: SceneDeckItem }) {
  const points = item.points.map((point) => point.position);
  const { center, size } = deckBoxPose(item);
  const worldCenter = toWorldPosition(center);
  const yawRadians = getDeckYawRadians(item);

  if (item.render_kind === "vial") {
    const diameter = Number(item.render_meta.diameter_mm ?? item.dimensions.length_mm ?? 14);
    const height = Number(item.render_meta.height_mm ?? item.dimensions.height_mm ?? 30);
    const baseAnchored = item.parent_id !== null;
    return (
      <group>
        <mesh
          position={toWorldPosition({
            ...item.primary_position,
            z: baseAnchored ? item.primary_position.z + height / 2 : item.primary_position.z,
          })}
        >
          <cylinderGeometry args={[diameter / 2, diameter / 2, height, 20]} />
          <meshStandardMaterial color="#d4a45f" roughness={0.45} metalness={0.05} />
        </mesh>
      </group>
    );
  }

  if (item.render_kind === "asset" && item.asset_path) {
    return (
      <AssetMesh
        assetPath={item.asset_path}
        fallbackCenter={worldCenter}
        fallbackSize={size}
        yawRadians={yawRadians}
      />
    );
  }

  const boxColor = item.render_kind === "well_plate" ? "#e8f0f3" : item.render_kind === "tip_rack" ? "#dec8a8" : "#a1b4ad";
  return (
    <group>
      <mesh position={worldCenter} rotation={[0, yawRadians, 0]}>
        <boxGeometry args={size} />
        <meshStandardMaterial color={boxColor} transparent opacity={0.72} roughness={0.8} />
      </mesh>
      {points.map((point) => (
        <Sphere key={`${item.id}:${point.x}:${point.y}:${point.z}`} args={[1.2, 12, 12]} position={toWorldPosition(point)}>
          <meshStandardMaterial color="#9a2b26" />
        </Sphere>
      ))}
    </group>
  );
}

function AssetMesh({
  assetPath,
  fallbackCenter,
  fallbackSize,
  yawRadians,
}: {
  assetPath: string;
  fallbackCenter: [number, number, number];
  fallbackSize: [number, number, number];
  yawRadians: number;
}) {
  try {
    const gltf = useGLTF(assetPath);
    const scene = gltf.scene.clone();
    return (
      <primitive
        object={scene}
        position={fallbackCenter}
        rotation={[-Math.PI / 2, yawRadians, 0]}
      />
    );
  } catch {
    return (
      <mesh position={fallbackCenter} rotation={[0, yawRadians, 0]}>
        <boxGeometry args={fallbackSize} />
        <meshStandardMaterial color="#7c8c86" transparent opacity={0.65} />
      </mesh>
    );
  }
}

function InstrumentStick({
  instrument,
  gantryPose,
  tipPose,
  volume,
}: {
  instrument: SceneInstrument;
  gantryPose: Pose;
  tipPose: Pose;
  volume: WorkingVolume;
}) {
  const outside = !isPointInsideVolume(gantryPose, volume) || !isPointInsideVolume(tipPose, volume);
  return (
    <group>
      <Line
        points={[toWorldPosition(gantryPose), toWorldPosition(tipPose)]}
        color={outside ? "#647a74" : "#1d1a15"}
        transparent
        opacity={outside ? 0.4 : 0.9}
        lineWidth={2}
      />
      <Sphere args={[2.3, 16, 16]} position={toWorldPosition(tipPose)}>
        <meshStandardMaterial color={outside ? "#6a7f79" : "#e6683c"} />
      </Sphere>
    </group>
  );
}

function TwinScene({
  bundle,
  toggles,
  gantryPose,
  instrumentTips,
  pathPoints,
}: {
  bundle: TwinBundle;
  toggles: ViewerToggles;
  gantryPose: Pose;
  instrumentTips: Record<string, Pose>;
  pathPoints: Pose[];
}) {
  const sceneBounds = useMemo(() => {
    const volume = bundle.scene.gantry.working_volume;
    const points: Pose[] = [
      { x: volume.x_min, y: volume.y_min, z: volume.z_min },
      { x: volume.x_max, y: volume.y_max, z: volume.z_max },
      ...bundle.scene.deck.flatMap((item) => item.points.map((point) => point.position)),
      ...Object.values(instrumentTips),
      gantryPose,
    ];
    return {
      center: poseCenter(points),
      spread: poseSpread(points, 20),
    };
  }, [bundle.scene.deck, bundle.scene.gantry.working_volume, gantryPose, instrumentTips]);

  return (
    <Canvas className="viewer-canvas" shadows>
      <PerspectiveCamera
        makeDefault
        position={[
          sceneBounds.center.x - sceneBounds.spread[0] * 0.8,
          sceneBounds.spread[0] * 0.7 + 80,
          sceneBounds.center.y + sceneBounds.spread[2] * 1.1,
        ]}
        fov={38}
      />
      <color attach="background" args={["#ebe6d8"]} />
      <ambientLight intensity={0.9} />
      <directionalLight position={[120, 180, 120]} intensity={1.1} castShadow />
      <OrbitControls makeDefault />
      <Bounds fit clip observe margin={1.25}>
        <group>
          {toggles.showGrid ? (
            <Grid
              position={toWorldPosition({ x: 200, y: 150, z: 0 })}
              args={[420, 320]}
              cellSize={20}
              cellThickness={0.5}
              sectionSize={100}
              sectionThickness={1}
              cellColor="#6f7f78"
              sectionColor="#2e5b51"
              fadeDistance={800}
              fadeStrength={1}
              infiniteGrid={false}
            />
          ) : null}
          <OriginMarker />
          {toggles.showWorkingVolume ? (
            <WorkingVolumeFrame volume={bundle.scene.gantry.working_volume} />
          ) : null}
          {bundle.scene.deck.map((item) => (
            <DeckItemMesh key={item.id} item={item} />
          ))}
          {toggles.showGantryPath && pathPoints.length > 1 ? (
            <Line
              points={pathPoints.map((point) => toWorldPosition(point))}
              color="#1d1a15"
              transparent
              opacity={0.55}
              lineWidth={1.5}
            />
          ) : null}
          <Sphere args={[3.2, 18, 18]} position={toWorldPosition(gantryPose)}>
            <meshStandardMaterial color="#2c9187" />
          </Sphere>
          {toggles.showInstrumentOffsets
            ? bundle.scene.instruments.map((instrument) => (
                <InstrumentStick
                  key={instrument.id}
                  instrument={instrument}
                  gantryPose={gantryPose}
                  tipPose={instrumentTips[instrument.id]}
                  volume={bundle.scene.gantry.working_volume}
                />
              ))
            : null}
        </group>
      </Bounds>
    </Canvas>
  );
}

function App() {
  const [bundle, setBundle] = useState<TwinBundle | null>(null);
  const [error, setError] = useState<string>("");
  const [isPlaying, setIsPlaying] = useState(false);
  const [speedMultiplier, setSpeedMultiplier] = useState(1);
  const [timeSeconds, setTimeSeconds] = useState(0);
  const [toggles, setToggles] = useState<ViewerToggles>({
    showGrid: true,
    showWorkingVolume: true,
    showGantryPath: true,
    showInstrumentOffsets: true,
  });
  const animationFrameRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(DEFAULT_BUNDLE_PATH)
      .then(async (response) => {
        if (!response.ok) {
          return;
        }
        const nextBundle = (await response.json()) as TwinBundle;
        if (!cancelled) {
          setBundle(nextBundle);
          setError("");
        }
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isPlaying || !bundle) {
      return;
    }

    let lastFrame = performance.now();
    const totalDuration = getTotalDuration(bundle);

    const tick = (now: number) => {
      const deltaSeconds = (now - lastFrame) / 1000;
      lastFrame = now;
      setTimeSeconds((current) => {
        const next = current + deltaSeconds * speedMultiplier;
        if (next >= totalDuration) {
          setIsPlaying(false);
          return totalDuration;
        }
        return next;
      });
      animationFrameRef.current = window.requestAnimationFrame(tick);
    };

    animationFrameRef.current = window.requestAnimationFrame(tick);
    return () => {
      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [bundle, isPlaying, speedMultiplier]);

  const sample = useMemo(() => {
    if (!bundle) {
      return null;
    }
    return samplePlayback(bundle, timeSeconds);
  }, [bundle, timeSeconds]);

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    try {
      const nextBundle = JSON.parse(await file.text()) as TwinBundle;
      setBundle(nextBundle);
      setTimeSeconds(0);
      setIsPlaying(false);
      setError("");
    } catch (parseError) {
      setError(`Failed to parse bundle: ${String(parseError)}`);
    }
  };

  const totalDuration = bundle ? getTotalDuration(bundle) : 0;
  const activeEvent = sample?.currentEvent ?? null;
  const activeMotion = currentMotionEvent(activeEvent);

  return (
    <div className="app-shell">
      <aside className="control-panel">
        <h1 className="panel-title">CubOS Twin</h1>
        <p className="panel-subtitle">
          Browser replay for exported CubOS traces. Phase 1 focuses on gantry-center motion, deck geometry, and offset instrument sticks.
        </p>
        <div className="stack">
          <section className="card">
            <h2>Bundle</h2>
            <div className="hud-item">
              <span className="hud-label">Default example</span>
              <span className="hud-value">{bundle ? DEFAULT_BUNDLE_PATH : "Load a JSON bundle"}</span>
            </div>
            <input className="file-input" type="file" accept="application/json" onChange={handleFileChange} />
            {error ? <p className="error">{error}</p> : null}
          </section>

          <section className="card">
            <h2>Summary</h2>
            <div className="summary-grid">
              <div className="summary-metric">
                <strong>{bundle?.summary.step_count ?? 0}</strong>
                Steps
              </div>
              <div className="summary-metric">
                <strong>{bundle?.summary.timeline_event_count ?? 0}</strong>
                Events
              </div>
              <div className="summary-metric">
                <strong>{totalDuration.toFixed(2)}s</strong>
                Replay
              </div>
            </div>
          </section>

          <section className="card">
            <h2>Playback</h2>
            <div className="control-row">
              <button type="button" onClick={() => setIsPlaying((current) => !current)} disabled={!bundle}>
                {isPlaying ? "Pause" : "Play"}
              </button>
              <button
                className="secondary"
                type="button"
                onClick={() => {
                  setTimeSeconds(0);
                  setIsPlaying(false);
                }}
                disabled={!bundle}
              >
                Reset
              </button>
            </div>
            <input
              className="slider"
              type="range"
              min={0}
              max={totalDuration || 0}
              step={0.01}
              value={Math.min(timeSeconds, totalDuration)}
              onChange={(event) => setTimeSeconds(Number(event.target.value))}
              disabled={!bundle}
            />
            <div className="control-row">
              <label htmlFor="speed">Speed</label>
              <input
                id="speed"
                type="range"
                min={0.25}
                max={4}
                step={0.25}
                value={speedMultiplier}
                onChange={(event) => setSpeedMultiplier(Number(event.target.value))}
              />
              <span>{speedMultiplier.toFixed(2)}x</span>
            </div>
          </section>

          <section className="card">
            <h2>Visibility</h2>
            <div className="toggle-grid">
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={toggles.showGrid}
                  onChange={(event) =>
                    setToggles((current) => ({ ...current, showGrid: event.target.checked }))
                  }
                />
                Grid Lines
              </label>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={toggles.showWorkingVolume}
                  onChange={(event) =>
                    setToggles((current) => ({ ...current, showWorkingVolume: event.target.checked }))
                  }
                />
                Working Volume
              </label>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={toggles.showGantryPath}
                  onChange={(event) =>
                    setToggles((current) => ({ ...current, showGantryPath: event.target.checked }))
                  }
                />
                Gantry Path
              </label>
              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={toggles.showInstrumentOffsets}
                  onChange={(event) =>
                    setToggles((current) => ({ ...current, showInstrumentOffsets: event.target.checked }))
                  }
                />
                Instrument Offsets
              </label>
            </div>
          </section>
        </div>
      </aside>

      <main className="viewer-shell">
        {bundle && sample ? (
          <>
            <TwinScene
              bundle={bundle}
              toggles={toggles}
              gantryPose={sample.gantryPose}
              instrumentTips={sample.instrumentTips}
              pathPoints={sample.pathPoints}
            />
            <div className="viewer-overlay">
              <div className="card">
                <span className="status-pill">{phaseLabel(activeEvent)}</span>
                <div className="stack">
                  <div className="hud-item">
                    <span className="hud-label">Current Step</span>
                    <span className="hud-value">{currentStepLabel(activeEvent)}</span>
                  </div>
                  <div className="hud-item">
                    <span className="hud-label">Target</span>
                    <span className="hud-value">{currentTargetLabel(activeEvent)}</span>
                  </div>
                  <div className="hud-item">
                    <span className="hud-label">Clock</span>
                    <span className="hud-value">
                      {sample.currentTime.toFixed(2)}s / {sample.totalDuration.toFixed(2)}s
                    </span>
                  </div>
                  {activeMotion ? (
                    <div className="hud-item">
                      <span className="hud-label">Motion</span>
                      <span className="hud-value">
                        {activeMotion.phase} at {activeMotion.feed_rate.toFixed(0)} mm/min
                      </span>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="viewer-overlay">
            <div className="card">
              <span className="status-pill">No bundle</span>
              <p>Load an exported digital twin JSON bundle to start the replay viewer.</p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
