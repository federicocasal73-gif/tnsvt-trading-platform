/**
 * Domain types shared between modules.
 * Kept tiny and dependency-free so any module can import without pulling React.
 */

export interface Tick {
  symbol: string;
  bid: number;
  ask: number;
  last: number;
  volume: number;
  source: string;
  /** ISO 8601 timestamp from the upstream source. */
  timestamp: string;
}