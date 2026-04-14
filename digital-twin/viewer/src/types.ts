export type Pose = {
  x: number;
  y: number;
  z: number;
};

export type WorkingVolume = {
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
  z_min: number;
  z_max: number;
};

export type SceneDeckPoint = {
  id: string;
  position: Pose;
};

export type SceneDeckItem = {
  id: string;
  parent_id: string | null;
  type: string;
  name: string;
  model_name: string;
  render_kind: "asset" | "well_plate" | "tip_rack" | "vial" | "bounding_box";
  asset_path: string | null;
  primary_position: Pose;
  dimensions: {
    length_mm: number | null;
    width_mm: number | null;
    height_mm: number | null;
  };
  points: SceneDeckPoint[];
  render_meta: Record<string, unknown>;
};

export type SceneInstrument = {
  id: string;
  type: string;
  vendor: string;
  offset_x: number;
  offset_y: number;
  depth: number;
  measurement_height: number;
  initial_tip_pose: Pose;
};

export type MotionEvent = {
  type: "motion";
  step_index: number;
  command: string;
  phase: string;
  instrument_id: string;
  target_label: string;
  start_gantry_pose: Pose;
  end_gantry_pose: Pose;
  start_tip_pose: Pose;
  end_tip_pose: Pose;
  feed_rate: number;
  distance_mm: number;
  real_duration_s: number;
  display_duration_s: number;
};

export type ActionEvent = {
  type: "action";
  step_index: number;
  command: string;
  kind: string;
  instrument_id: string | null;
  target_label: string | null;
  duration_s: number;
  payload: Record<string, unknown>;
};

export type DwellEvent = {
  type: "dwell";
  step_index: number;
  command: string;
  duration_s: number;
  label: string;
};

export type TimelineEvent = MotionEvent | ActionEvent | DwellEvent;

export type TwinBundle = {
  scene: {
    gantry: {
      working_volume: WorkingVolume;
      homing_strategy: string;
      y_axis_motion: string;
      initial_gantry_pose: Pose;
      safe_z_height: number;
      max_z_height: number;
    };
    deck: SceneDeckItem[];
    instruments: SceneInstrument[];
  };
  timeline: TimelineEvent[];
  summary: {
    step_count: number;
    timeline_event_count: number;
    total_display_duration_s: number;
  };
};
