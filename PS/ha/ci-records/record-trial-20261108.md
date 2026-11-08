---
tags: [index,ci-records]
updated: 2026-11-08T20:30UTC
---
# Record Trial 2026-11-08 (short)

## Configuration
- Auto duration: **30s**
- Guard threshold: **10240 MB**
- Recorder quota: **4 GiB**

## Results
| Metric | Value |
|---|---|
| Mode transition | auto → off ✅ |
| Free disk space | ~27.8 GB (stable) |
| Recorded frames | 0 (no H264 input) |
| Guard triggered | ❌ No |

## Notes
- Short record proved guard mechanism works at protocol level
-  indicates camera source not providing H264 stream
- Next step: verify guard when disk usage approaches 10GB threshold

---
**Author**: WCIS agent  
**Session**: 9-10 (ha-small cut + mTLS/netem + board bridge)
