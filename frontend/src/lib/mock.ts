export type Severity = "critical" | "high" | "medium" | "low";

export type Bug = {
  id: string;
  title: string;
  severity: Severity;
  summary: string;
  steps: string[];
};

export type RunStatus = "PASSED" | "BUGS_FOUND" | "BLOCKED" | "AUTH_REQUIRED" | "ERROR";

export type RunHistoryItem = {
  id: string;
  deploy: string;
  date: string;
  status: RunStatus;
  bugs: number;
  steps: number;
};

export const liveSteps: string[] = [
  "Opened the home page",
  "Clicked the Sign up button",
  "Submitted the form with an empty email",
  "Submitted the form with an emoji-only name",
  "Double-clicked the Pay button quickly",
  "Pressed the browser back button mid-checkout",
  "Resized the window to phone width and retried checkout",
  "Pasted 10,000 characters into the address field",
];

export const bugs: Bug[] = [
  {
    id: "BUG-1",
    title: "Double-click on Pay creates two orders",
    severity: "critical",
    summary: "Clicking Pay twice within a second submits the order twice and charges twice.",
    steps: ["Add any item to cart", "Go to checkout", "Double-click Pay"],
  },
  {
    id: "BUG-2",
    title: "Empty email passes validation",
    severity: "high",
    summary: "The sign-up form accepts an empty email and shows a success message.",
    steps: ["Open Sign up", "Leave email empty", "Click Submit"],
  },
  {
    id: "BUG-3",
    title: "Back button loses the cart",
    severity: "medium",
    summary: "Going back from checkout empties the cart without any warning.",
    steps: ["Add an item", "Open checkout", "Press browser Back"],
  },
  {
    id: "BUG-4",
    title: "Long address overflows the card",
    severity: "low",
    summary: "A very long address text runs outside the summary card on small screens.",
    steps: ["Open checkout on a phone-width window", "Paste a very long address"],
  },
];

export const history: RunHistoryItem[] = [
  { id: "run-005", deploy: "v0.5", date: "2 Nov", status: "BUGS_FOUND", bugs: 4, steps: 8 },
  { id: "run-004", deploy: "v0.4", date: "1 Nov", status: "BUGS_FOUND", bugs: 6, steps: 11 },
  { id: "run-003", deploy: "v0.3", date: "31 Oct", status: "AUTH_REQUIRED", bugs: 0, steps: 2 },
  { id: "run-002", deploy: "v0.2", date: "30 Oct", status: "BLOCKED", bugs: 0, steps: 1 },
  { id: "run-001", deploy: "v0.1", date: "29 Oct", status: "PASSED", bugs: 0, steps: 9 },
];
