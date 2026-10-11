export type EnterBehavior = "send" | "newline";
const enterKey = "scholartrace.enter-behavior.v1";
const tutorialKey = "scholartrace.tutorial.v1";
export function readEnterBehavior(): EnterBehavior {
  try {
    return localStorage.getItem(enterKey) === "newline" ? "newline" : "send";
  } catch {
    return "send";
  }
}
export function saveEnterBehavior(value: EnterBehavior) {
  try {
    localStorage.setItem(enterKey, value);
  } catch {
    /* Keep current-tab preference. */
  }
}
export function shouldShowTutorial() {
  try {
    return localStorage.getItem(tutorialKey) !== "seen";
  } catch {
    return true;
  }
}
export function markTutorialSeen() {
  try {
    localStorage.setItem(tutorialKey, "seen");
  } catch {
    /* Help stays available without storage. */
  }
}
