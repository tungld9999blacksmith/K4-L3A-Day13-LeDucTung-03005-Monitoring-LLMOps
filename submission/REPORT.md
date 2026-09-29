# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Lê Đức Tùng
- **MSSV:** 03005
- **Lớp:** K4-L3A
- **Repository URL:** <https://github.com/tungld9999blacksmith/K4-L3A-Day13-LeDucTung-03005-Monitoring-LLMOps>
- **Commit SHA cuối:** _(điền ở CP4)_
- **Challenge ID:** _(điền ở CP3)_
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-03005`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 (`data/logs.baseline.jsonl`, 47 records) | 100/100 (129 records, 60 correlation ID) | Baseline thiếu `correlation_id` và enrichment; sau CP1 đạt đủ 4 tiêu chí |
| `validate_dashboard.py` | HỢP LỆ 6/6 | HỢP LỆ 6/6 | Contract có sẵn; dashboard runtime xem mục 6 |
| `pytest` | _(điền)_ | 25 passed | |
| Số traces hợp lệ | 0 (tracing chưa bật) | ≥ 10 _(điền số thực tế từ Langfuse)_ | Mỗi trace có root + retrieval + generation |
| Số PII leak | 0 | 0 | Theo `validate_logs.py` |
| Latency P95 / TTFT P95 | 1288 ms / 52 ms | 1265 ms / 50 ms | Dưới ngưỡng SLO 3000 ms |
| Retrieval success rate | _(điền)_ | 100% (60/60) | Guardrail ≥ 90% |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** [`app/middleware.py`](../app/middleware.py) xóa contextvars cũ bằng `clear_contextvars()`, lấy ID từ header request hoặc sinh mới theo format `req-<8-hex>`, `bind_contextvars(correlation_id=...)` để mọi log trong request tự có ID, lưu vào `request.state` để truyền sang `LabAgent.run` (đưa vào metadata trace) và trả lại trong response header.
- **Các metadata được ghi vào structured log:** `ts`, `level`, `service`, `event`, `env`, `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`; event `response_sent` có thêm `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** processor `scrub_event` ([`app/logging_config.py`](../app/logging_config.py)) được đăng ký trong chuỗi structlog **trước** `JSONRenderer`/file writer, chạy `scrub_text` ([`app/pii.py`](../app/pii.py)) cho email, số điện thoại VN, CCCD/CMND, thẻ tín dụng, passport, IPv4, API key, bearer token. `user_id` chỉ lưu dạng SHA-256 rút gọn 12 ký tự.
- **Cách kiểm chứng kết quả:** `python scripts/validate_logs.py` (0 PII leak, 100/100), unit test trong [`tests/test_pii.py`](../tests/test_pii.py), và kiểm tra `data/logs.jsonl` chỉ còn `[REDACTED_EMAIL]`...

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** traces nằm trong project `day13-k4-l3a-03005`; `correlation_id` trong metadata trace (vd. `req-f1bf9512`, `req-d60d27c2`) trùng với `correlation_id` trong `data/logs.jsonl` do chính máy tôi ghi khi chạy `python scripts/load_test.py`.
- **Cấu trúc root/retrieval/generation observations:** mỗi request tạo trace `day13-agent-request` gồm:
  - `lab-agent-run` (type `agent`, root, `@observe` trên `LabAgent.run`, không capture raw input/output);
  - `retrieval` (type `retriever`, [`app/mock_rag.py`](../app/mock_rag.py)) — input là query đã scrub, output là docs;
  - `llm-generation` (type `generation`, [`app/mock_llm.py`](../app/mock_llm.py)) — có `model`, prompt đã scrub, `usage_details` (input/output tokens), `cost_details` và link tới managed prompt.

  `propagate_attributes` gắn `user_id` (đã hash), `session_id`, `environment`, tags và metadata `feature`, `model`, `correlation_id` cho mọi observation. Ví dụ trace `10ddf55526a4e5e82fed1e17b5ec2161`: tổng 153 ms, retrieval 1 ms, llm-generation 152 ms, cost $0.001818, 150 tokens, prompt `day13-chat - v1` ⇒ LLM là bước chậm.
- **Cách nối trace với log:** lấy `correlation_id` từ log `response_sent` trong `data/logs.jsonl`, lọc metadata `correlation_id` trên Langfuse để ra đúng trace; ngược lại đọc `correlation_id` trong metadata trace để grep log.
- **Prompt name:** `day13-chat` (text prompt, giữ 3 biến `{{feature}}`, `{{docs}}`, `{{message}}`)
- **Version/label baseline:** v1 — labels `baseline`, `production`
- **Version/label candidate:** v2 — label `candidate` _(mô tả thay đổi nhỏ, vd. thêm "Answer in at most 2 sentences.")_
- **Trace ID của mỗi version:** v1/`baseline`: `<trace-id>` · v2/`candidate`: `<trace-id>` (cùng input `<input>`)
- **Cách promote và rollback `production`:** trên Langfuse Prompts, chuyển label `production` từ v1 sang v2, chạy lại một request với `LANGFUSE_PROMPT_LABEL=production` (trace `<trace-id>` cho `prompt_version=2`); sau đó chuyển `production` về v1 (rollback) và chạy lại (trace `<trace-id>` cho `prompt_version=1`). App cache prompt 60 giây nên restart API/đợi 60s sau mỗi lần đổi label. Evidence: [`evidence/10-prompt-rollback.png`](evidence/10-prompt-rollback.png).

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** _(điền công cụ và đường dẫn source dashboard)_ đọc `data/logs.jsonl` theo contract [`config/dashboard.yaml`](../config/dashboard.yaml): latency P50/P95/P99 + TTFT P95 (ms, threshold P95 ≤ 3000), traffic (requests/phút, ≥ 1), error rate + breakdown + retrieval success (%, ≤ 2), cost (USD, tổng ≤ 2.5), tokens in/out (tokens, ≤ 50000), quality proxy (0–1, mean ≥ 0.75); time range 60 phút, refresh 30s. Evidence: [`evidence/11-dashboard-overview.png`](evidence/11-dashboard-overview.png).
- **SLO và lý do chọn:** `fast_successful_requests` — 99.5% request trả về thành công với latency ≤ 3000 ms trong cửa sổ 28 ngày ([`config/slo.yaml`](../config/slo.yaml)). Baseline 81 request: P50 153 ms, P95 1265 ms, P99 1284 ms, max 2536 ms, 0 lỗi. Ngưỡng 3000 ms cao hơn P95 khoảng 2 lần nên không gây báo động giả, nhưng vẫn bắt được incident `rag_slow` (+2.5 s). Target 99.5% cân bằng giữa 99.9% (quá chặt với lượng request nhỏ) và 99% (quá lỏng với chatbot).
- **Cách tính error budget:** budget = 100% − 99.5% = 0.5%, tức 5 request xấu trên 1000 request, hoặc 0.5% × 28 × 24 × 60 = 201.6 phút (khoảng 3.36 giờ) mỗi 28 ngày. Nếu dùng quá 50% budget trong 7 ngày: dừng promote prompt/model mới và ưu tiên sửa độ tin cậy. Nếu dùng hết 100%: freeze release, chỉ rollback hoặc hotfix.
- **Ba alert và runbook tương ứng:** định nghĩa trong [`config/alert_rules.yaml`](../config/alert_rules.yaml), runbook trong [`docs/alerts.md`](../docs/alerts.md):
  1. `HighLatencyP95` (P2, 5m): P95 latency > 3000 ms, gắn với SLO `fast_successful_requests`.
  2. `HighErrorRate` (P1, 5m): error rate > 2% hoặc retrieval success < 90%.
  3. `CostBurnRateHigh` (P3, 15m): cost trong 1 giờ > 0.104 USD, tức vượt guardrail 2.5 USD/ngày nếu giữ tốc độ đó.

  Cả ba alert đều dựa trên triệu chứng người dùng thấy, gửi về Slack `#day13-l3a-alerts`, owner Lê Đức Tùng.

## 7. Điều tra challenge

- **Challenge ID:**
- **Khoảng thời gian điều tra:**
- **Triệu chứng từ metrics:**
- **Log line và correlation ID liên quan:**
- **Trace ID và span gây ảnh hưởng:**
- **Root cause:**
- **Fix action:**
- **Preventive measure:**

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
- **Một lỗi/blocker đã gặp:**
- **Cách tìm nguyên nhân và xử lý:**
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
