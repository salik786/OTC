export type Screen = "setup" | "welcome" | "listening" | "core-info" | "qa" | "closing";

export interface QATurn {
  turnNumber: number;
  queryText: string;
  answerText: string;
  inScope: boolean;
}
