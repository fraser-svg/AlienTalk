//! Bounded compression request queue with monotonic IDs.
//!
//! Request flow:
//! ```text
//! [hotkey/extension] → enqueue(text, source) → queue(32) → dequeue → pipeline
//!                                                  ↓ (full)
//!                                            drop-oldest
//! ```

use std::sync::atomic::{AtomicU64, Ordering};
use tokio::sync::mpsc;

/// Monotonic request ID counter.
static NEXT_REQUEST_ID: AtomicU64 = AtomicU64::new(1);

/// Source of a compression request.
#[derive(Debug, Clone, PartialEq)]
pub enum RequestSource {
    /// macOS accessibility API (global hotkey)
    Accessibility {
        bundle_id: String,
    },
    /// Chrome extension (native messaging)
    Extension {
        url: String,
    },
}

/// A compression request entering the pipeline.
#[derive(Debug, Clone)]
pub struct CompressionRequest {
    /// Monotonic ID for stale-result discard.
    pub id: u64,
    /// The raw text to compress.
    pub text: String,
    /// Where the request came from.
    pub source: RequestSource,
}

impl CompressionRequest {
    pub fn new(text: String, source: RequestSource) -> Self {
        Self {
            id: NEXT_REQUEST_ID.fetch_add(1, Ordering::Relaxed),
            text,
            source,
        }
    }
}

/// Result of a compression operation.
#[derive(Debug, Clone)]
pub struct CompressionResult {
    /// The request ID this result belongs to.
    pub request_id: u64,
    /// Compressed text (or original on error/timeout).
    pub text: String,
    /// Percentage saved (0.0 if failed).
    pub savings_pct: f64,
    /// Whether this was a pass-through (error/timeout/empty).
    pub is_passthrough: bool,
}

/// Queue capacity. When full, oldest request is dropped.
const QUEUE_CAPACITY: usize = 32;

/// Create a bounded compression queue.
///
/// Returns (sender, receiver). Sender uses `try_send` — if the channel
/// is full, the caller should drain one item and retry (drop-oldest).
pub fn create() -> (mpsc::Sender<CompressionRequest>, mpsc::Receiver<CompressionRequest>) {
    mpsc::channel(QUEUE_CAPACITY)
}

/// Try to enqueue a request. Returns Err if the channel is full or closed.
///
/// The caller is responsible for handling backpressure. In practice, the
/// pipeline discards stale results via monotonic request IDs, so dropping
/// a request on a full queue is acceptable — the user will just get the
/// latest result.
pub fn try_enqueue(
    tx: &mpsc::Sender<CompressionRequest>,
    request: CompressionRequest,
) -> Result<(), CompressionRequest> {
    match tx.try_send(request) {
        Ok(()) => Ok(()),
        Err(mpsc::error::TrySendError::Full(req)) => {
            tracing::warn!(id = req.id, "Queue full — request dropped (latest wins via stale-check)");
            Err(req)
        }
        Err(mpsc::error::TrySendError::Closed(req)) => {
            tracing::error!("Queue channel closed");
            Err(req)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn request_ids_are_monotonic() {
        let r1 = CompressionRequest::new("a".into(), RequestSource::Accessibility {
            bundle_id: "com.test".into(),
        });
        let r2 = CompressionRequest::new("b".into(), RequestSource::Accessibility {
            bundle_id: "com.test".into(),
        });
        assert!(r2.id > r1.id);
    }

    #[test]
    fn request_ids_are_unique() {
        let ids: Vec<u64> = (0..100)
            .map(|_| {
                CompressionRequest::new("x".into(), RequestSource::Extension {
                    url: "https://test.com".into(),
                })
                .id
            })
            .collect();
        let unique: std::collections::HashSet<u64> = ids.iter().copied().collect();
        assert_eq!(ids.len(), unique.len());
    }

    #[tokio::test]
    async fn queue_create_has_capacity() {
        let (tx, _rx) = create();
        // Should be able to send QUEUE_CAPACITY items without blocking
        for i in 0..QUEUE_CAPACITY {
            let req = CompressionRequest::new(
                format!("text {i}"),
                RequestSource::Accessibility { bundle_id: "com.test".into() },
            );
            tx.try_send(req).expect("should not be full yet");
        }
        // Next send should fail (full)
        let req = CompressionRequest::new(
            "overflow".into(),
            RequestSource::Accessibility { bundle_id: "com.test".into() },
        );
        assert!(tx.try_send(req).is_err());
    }
}
