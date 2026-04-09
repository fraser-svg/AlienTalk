/**
 * AlienTalk — Word-level diff algorithm.
 *
 * Computes a minimal diff between original and compressed text using
 * longest common subsequence (LCS) on word tokens. Preserves whitespace
 * by attaching it to preceding words.
 */

/**
 * Tokenize text into words with trailing whitespace attached.
 * "hello  world" → ["hello  ", "world"]
 * @param {string} text
 * @returns {string[]}
 */
function tokenize(text) {
  const tokens = [];
  const re = /\S+\s*/g;
  let match;
  while ((match = re.exec(text)) !== null) {
    tokens.push(match[0]);
  }
  return tokens;
}

/**
 * Build LCS table for two token arrays.
 * @param {string[]} a
 * @param {string[]} b
 * @returns {number[][]}
 */
function lcsTable(a, b) {
  const m = a.length;
  const n = b.length;
  // dp[i][j] = LCS length for a[0..i-1], b[0..j-1]
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }
  return dp;
}

/**
 * Backtrack through LCS table to produce diff operations.
 * @param {number[][]} dp
 * @param {string[]} a - original tokens
 * @param {string[]} b - compressed tokens
 * @param {number} i
 * @param {number} j
 * @returns {Array<{type: 'equal'|'removed'|'added', text: string}>}
 */
function backtrack(dp, a, b, i, j) {
  const result = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      result.push({ type: "equal", text: a[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.push({ type: "added", text: b[j - 1] });
      j--;
    } else {
      result.push({ type: "removed", text: a[i - 1] });
      i--;
    }
  }

  return result.reverse();
}

/**
 * Merge consecutive diff entries of the same type for cleaner output.
 * @param {Array<{type: string, text: string}>} ops
 * @returns {Array<{type: string, text: string}>}
 */
function mergeOps(ops) {
  if (ops.length === 0) return ops;
  const merged = [ops[0]];
  for (let i = 1; i < ops.length; i++) {
    const last = merged[merged.length - 1];
    if (ops[i].type === last.type) {
      last.text += ops[i].text;
    } else {
      merged.push({ ...ops[i] });
    }
  }
  return merged;
}

/**
 * Compute a word-level diff between original and compressed text.
 * @param {string} original
 * @param {string} compressed
 * @returns {Array<{type: 'equal'|'removed'|'added', text: string}>}
 */
/**
 * Max tokens before skipping LCS (prevents O(n*m) OOM on large prompts).
 */
const MAX_DIFF_TOKENS = 500;

function computeDiff(original, compressed) {
  const a = tokenize(original);
  const b = tokenize(compressed);

  // Guard against OOM: LCS table is O(n*m) in memory
  if (a.length > MAX_DIFF_TOKENS || b.length > MAX_DIFF_TOKENS) {
    // Fall back to simple removed/added for large inputs
    return [
      { type: "removed", text: original },
      { type: "added", text: compressed },
    ];
  }

  const dp = lcsTable(a, b);
  const ops = backtrack(dp, a, b, a.length, b.length);
  return mergeOps(ops);
}
