# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

Cấu hình máy đọc được nằm ở [`../config/alert_rules.yaml`](../config/alert_rules.yaml); SLO và guardrail ở [`../config/slo.yaml`](../config/slo.yaml).

## Alert 1

- Tên: `HighLatencyP95`
- Severity: P2 (ảnh hưởng trải nghiệm, chưa mất chức năng)
- Duration: 5m
- Kênh thông báo: Slack `#day13-l3a-alerts`
- SLI/SLO liên quan: `fast_successful_requests` — 99.5% request thành công với `latency_ms <= 3000` trong 28 ngày (error budget 0.5% ≈ 201.6 phút).
- Điều kiện và thời gian duy trì: P95 `latency_ms` của event `response_sent` > 3000 ms liên tục 5 phút. Baseline P95 ≈ 1.3 s nên vượt 3 s là bất thường rõ ràng.
- Ảnh hưởng tới người dùng: câu trả lời chậm > 3 s, người dùng có thể bỏ đi hoặc gửi lại request; mỗi request chậm tiêu vào error budget của SLO.
- Ba bước kiểm tra đầu tiên:
  1. Dashboard panel **Latency percentiles and TTFT**: xác định thời điểm P95 tăng; so sánh TTFT P95 — TTFT bình thường mà latency tăng thì chậm nằm trước/ngoài LLM (vd. retrieval).
  2. Lọc `data/logs.jsonl` các `response_sent` có `latency_ms > 3000` trong khoảng đó, lấy vài `correlation_id`; kiểm tra có tập trung theo `feature`/`model` không.
  3. Mở trace có cùng `correlation_id` trong Langfuse, xem Timeline: span `retrieval` hay `llm-generation` chiếm phần lớn thời gian.
- Mitigation tạm thời: nếu retrieval chậm → bật fallback trả lời không cần context / giảm timeout retrieval; nếu LLM chậm → chuyển model nhanh hơn hoặc rút ngắn prompt (rollback label `production` nếu vừa đổi prompt). Kiểm tra incident đang bật: `python scripts/inject_incident.py --scenario rag_slow --disable`.
- Owner: LeDucTung

## Alert 2

- Tên: `HighErrorRate`
- Severity: P1 (người dùng nhận lỗi, mất chức năng)
- Duration: 5m
- Kênh thông báo: Slack `#day13-l3a-alerts`
- SLI/SLO liên quan: `fast_successful_requests` (request lỗi là bad event) và guardrail `error_rate_pct_max: 2`, `retrieval_success_rate_pct_min: 90`.
- Điều kiện và thời gian duy trì: error rate = `request_failed / request_received * 100` > 2% **hoặc** retrieval success rate (`tool_success`) < 90%, liên tục 5 phút.
- Ảnh hưởng tới người dùng: request trả lỗi hoặc câu trả lời thiếu tài liệu tham chiếu; error budget bị tiêu rất nhanh (2% lỗi = 4x tốc độ cho phép của budget 0.5%).
- Ba bước kiểm tra đầu tiên:
  1. Dashboard panel **Error rate and retrieval success**: xem breakdown theo `error_type` và retrieval success có giảm cùng lúc không.
  2. Lọc log `request_failed` lấy `error_type`, `tool_name`, `correlation_id`; xác định lỗi đến từ một dependency (vd. `RuntimeError` từ vector store) hay rải rác.
  3. Mở trace cùng `correlation_id`: observation nào có level `ERROR` và `status_message` gì (vd. `retrieval` → "Vector store timeout").
- Mitigation tạm thời: nếu lỗi ở retrieval → trả lời fallback không dùng context, retry có giới hạn; nếu lỗi sau deploy/đổi prompt → rollback. Tắt incident luyện tập nếu đang bật: `python scripts/inject_incident.py --scenario tool_fail --disable`.
- Owner: LeDucTung

## Alert 3

- Tên: `CostBurnRateHigh`
- Severity: P3 (chưa ảnh hưởng chức năng, ảnh hưởng ngân sách)
- Duration: 15m
- Kênh thông báo: Slack `#day13-l3a-alerts`
- SLI/SLO liên quan: guardrail `daily_cost_usd_max: 2.5` USD/ngày ⇒ tốc độ cho phép ≈ 2.5 / 24 ≈ 0.104 USD/giờ.
- Điều kiện và thời gian duy trì: tổng `cost_usd` của `response_sent` trong 1 giờ gần nhất > 0.104 USD (tức nếu giữ tốc độ này sẽ vượt 2.5 USD/ngày), duy trì 15 phút.
- Ảnh hưởng tới người dùng: gián tiếp — vượt ngân sách có thể buộc phải rate-limit hoặc tắt tính năng; output quá dài cũng làm câu trả lời chậm và khó đọc.
- Ba bước kiểm tra đầu tiên:
  1. Dashboard panel **Cost over time** và **Input and output tokens**: cost tăng do traffic tăng (panel Request traffic) hay do token/request tăng.
  2. Lọc log `response_sent` có `tokens_out` / `cost_usd` cao bất thường, lấy `correlation_id`, kiểm tra theo `feature`, `model` và prompt version.
  3. Mở trace trong Langfuse: xem usage và cost của `llm-generation`, prompt version đang dùng có vừa đổi không.
- Mitigation tạm thời: giới hạn `max_tokens` output, rollback label `production` về prompt version trước nếu prompt mới làm output dài hơn, chuyển feature ít quan trọng sang model rẻ hơn, rate-limit user bất thường. Tắt incident luyện tập nếu đang bật: `python scripts/inject_incident.py --scenario cost_spike --disable`.
- Owner: LeDucTung
