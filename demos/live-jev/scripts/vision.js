// Vision variant of the driving questions: same keys and criteria as brain.js QUESTIONS, but the
// instructions point at the screenshot instead of the JSON perception fields.
import { createCanvas } from "@napi-rs/canvas";
import { CONFIG } from "../public/js/config.js";
import { Renderer } from "../public/js/render.js";
import { QUESTIONS } from "../public/js/brain.js";

export const SCREEN_LEGEND =
  "The image is a top-down view of a one-way road with 3 lanes (lane 0 is the leftmost). Ego is the blue car near the bottom centre, " +
  `driving upward; the view covers about ${Math.round(CONFIG.CANVAS_H * CONFIG.EGO_SCREEN_Y / CONFIG.PX_PER_M)} m ahead of ego at ${CONFIG.PX_PER_M} px per metre. ` +
  "Other cars are red or grey rectangles (grey with amber corners = parked), orange discs are traffic cones, red-and-white blocks are barriers, " +
  "small figures are pedestrians, the light strips on both sides are sidewalks. The HUD at the top shows ego's speed and lane.";

const VISION_INSTRUCTIONS = {
  lane_action:
    "You are the driving policy of ego. Decide the lane maneuver for the next second from the screenshot. Change lanes only if the target lane " +
    "exists (`ego.can_change_left` / `ego.can_change_right`), nothing is alongside ego in it, it is clearly more open ahead than the current lane, " +
    "and no car is closing from behind in it. Keep the lane when the current lane is clear, when `ego.lane_change_in_progress` is true, or when " +
    "`ego.seconds_since_lane_change` is below 3. If ego is stopped behind something that is also stopped, a lane change into any lane with a few " +
    "more metres of room is better than waiting. Plan double lane changes early when the current and adjacent lanes are both blocked but the far lane is open.",
  speed_action:
    "Decide how ego should adjust its speed in the next second, from the screenshot. Only ego's own lane matters for speed; objects in other lanes or " +
    "on the sidewalk are not a reason to slow down. Estimate the free distance ahead in ego's lane in metres and compare it with `ego.stopping_distance_m`. " +
    "Stop for pedestrians on or about to enter the road ahead. Slow down only when the free distance is under about twice the stopping distance or a " +
    "collision is a few seconds away. A slower lead that is still far away is not a reason to slow down yet. Speed up when the lane is clear and " +
    "speed is below `ego.max_speed_kmh`.",
  hazard: "Rate the overall collision hazard for ego right now, from the screenshot.",
  pedestrian_yield:
    "A pedestrian is on the road, or is walking toward the road and will reach ego's lane, within roughly `ego.stopping_distance_m` plus a safety " +
    "margin ahead of ego, so ego must stop and yield. Judge it from the screenshot.",
};
export const VISION_QUESTIONS = Object.fromEntries(Object.entries(QUESTIONS).map(([k, q]) => [k, { ...q, instructions: VISION_INSTRUCTIONS[k] }]));

/** Ego-only telemetry (odometry, no environment perception): what the car knows without the JSON sensors. */
export function egoTelemetry(state) {
  const e = state.ego;
  return { screen: SCREEN_LEGEND, ego: {
    speed_kmh: e.speed_kmh, max_speed_kmh: e.max_speed_kmh, lane: e.lane, stopping_distance_m: e.stopping_distance_m,
    can_change_left: e.can_change_left, can_change_right: e.can_change_right,
    lane_change_in_progress: e.lane_change_in_progress, seconds_since_lane_change: e.seconds_since_lane_change,
  } };
}

/** Renders the sim exactly as the browser does and returns a JPEG Buffer. The model's view has no ray or
 * answer overlays; pass overlays: true for video frames. */
export function makeScreenshotter({ overlays = false } = {}) {
  const canvas = createCanvas(CONFIG.CANVAS_W, CONFIG.CANVAS_H);
  canvas.getBoundingClientRect = () => ({}); // Renderer only asks for a 2D context when this exists
  const renderer = new Renderer(canvas);
  renderer.showRays = false; renderer.showAnswers = overlays;
  return (world, perception, ui) => { renderer.draw(world, perception, ui); return canvas.toBuffer("image/jpeg", 75); };
}
export const toDataUrl = (jpeg) => `data:image/jpeg;base64,${jpeg.toString("base64")}`;
