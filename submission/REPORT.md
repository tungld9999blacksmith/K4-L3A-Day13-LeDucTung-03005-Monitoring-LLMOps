# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Lê Đức Tùng
- **MSSV:** 03005
- **Lớp:** K4-L3A
- **Repository URL:** <https://github.com/tungld9999blacksmith/K4-L3A-Day13-LeDucTung-03005-Monitoring-LLMOps>
- **Commit SHA cuối:** b7695c3d38615012ea4da532e208819049403693
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
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

- **Dashboard và sáu panel:** Streamlit app [`dashboard/app.py`](../dashboard/app.py) (`streamlit run dashboard/app.py`), đọc tên panel, đơn vị, threshold, time range và refresh trực tiếp từ contract, tính toán trên `data/logs.jsonl` theo contract [`config/dashboard.yaml`](../config/dashboard.yaml): latency P50/P95/P99 + TTFT P95 (ms, threshold P95 ≤ 3000), traffic (requests/phút, ≥ 1), error rate + breakdown + retrieval success (%, ≤ 2), cost (USD, tổng ≤ 2.5), tokens in/out (tokens, ≤ 50000), quality proxy (0–1, mean ≥ 0.75); time range 60 phút, refresh 30s. Evidence: [`evidence/11-dashboard-overview.png`](evidence/11-dashboard-overview.png).
- **SLO và lý do chọn:** `fast_successful_requests` — 99.5% request trả về thành công với latency ≤ 3000 ms trong cửa sổ 28 ngày ([`config/slo.yaml`](../config/slo.yaml)). Baseline 81 request: P50 153 ms, P95 1265 ms, P99 1284 ms, max 2536 ms, 0 lỗi. Ngưỡng 3000 ms cao hơn P95 khoảng 2 lần nên không gây báo động giả, nhưng CP3 cho thấy ngưỡng này **không** bắt được incident `rag_slow` (P95 server-side 2667 ms < 3000 ms), vì vậy tôi đề xuất bổ sung cảnh báo 2000 ms và alert theo span retrieval (mục 7). Target 99.5% cân bằng giữa 99.9% (quá chặt với lượng request nhỏ) và 99% (quá lỏng với chatbot).
- **Cách tính error budget:** budget = 100% − 99.5% = 0.5%, tức 5 request xấu trên 1000 request, hoặc 0.5% × 28 × 24 × 60 = 201.6 phút (khoảng 3.36 giờ) mỗi 28 ngày. Nếu dùng quá 50% budget trong 7 ngày: dừng promote prompt/model mới và ưu tiên sửa độ tin cậy. Nếu dùng hết 100%: freeze release, chỉ rollback hoặc hotfix.
- **Ba alert và runbook tương ứng:** định nghĩa trong [`config/alert_rules.yaml`](../config/alert_rules.yaml), runbook trong [`docs/alerts.md`](../docs/alerts.md):
  1. `HighLatencyP95` (P2, 5m): P95 latency > 3000 ms, gắn với SLO `fast_successful_requests`.
  2. `HighErrorRate` (P1, 5m): error rate > 2% hoặc retrieval success < 90%.
  3. `CostBurnRateHigh` (P3, 15m): cost trong 1 giờ > 0.104 USD, tức vượt guardrail 2.5 USD/ngày nếu giữ tốc độ đó.

  Cả ba alert đều dựa trên triệu chứng người dùng thấy, gửi về Slack `#day13-l3a-alerts`, owner Lê Đức Tùng.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1` (cohort K4, 5 query, `feature=monitoring`, chạy `python scripts/inject_incident.py` + `python scripts/load_test.py --challenge --concurrency 5`).
- **Khoảng thời gian điều tra:** 2026-09-29 **11:37:00Z → 11:42:39Z (UTC)**, tính từ log `incident_enabled` (`req-25ca76d0`) đến `incident_disabled` (`req-db174438`); các request bị ảnh hưởng nằm trong khoảng 11:37:10Z–11:37:24Z.
- **Triệu chứng từ metrics:** panel **Latency P50/P95/P99** tăng vọt: **P95 = 2667 ms, P50 = 2653 ms** (5/5 request `monitoring`), trong khi ngay trước đó P50 là 153 ms và baseline P95 là 1265 ms, tức chậm hơn khoảng 17 lần. Mọi panel khác giữ nguyên: TTFT P95 = 50 ms (không đổi), error rate 0%, retrieval success 100%, cost trung bình khoảng $0.0022/request, quality 0.84. Từ đó suy ra độ chậm **không** nằm ở LLM (TTFT, token, cost không đổi) và cũng không phải lỗi (tool_success=true). Phần chậm thêm (khoảng 2.5 s) xảy ra trước khi LLM bắt đầu sinh token. Evidence: [`evidence/12-incident-metric.txt`](evidence/12-incident-metric.txt) · `evidence/12-incident-metric.png`.
- **Log line và correlation ID liên quan:** `req-f525d3a0` (evidence: [`evidence/13-incident-log.txt`](evidence/13-incident-log.txt))

  ```json
  {"service": "api", "latency_ms": 2653, "ttft_ms": 50, "tokens_in": 35, "tokens_out": 161, "cost_usd": 0.00252, "quality_score": 0.8, "tool_name": "retrieval", "tool_success": true, "event": "response_sent", "correlation_id": "req-f525d3a0", "session_id": "k4-l3a-challenge-s01", "feature": "monitoring", "level": "info", "ts": "2026-09-29T11:37:13.408557Z"}
  ```

  `latency_ms` = 2653, nhưng `ttft_ms` = 50 và lượng token bình thường. Cả 5 request trong khoảng này (`req-f525d3a0`, `req-6b252cb3`, `req-dda32216`, `req-d0f072c6`, `req-1b76119f`) đều có latency 2652–2667 ms. Một điểm đáng chú ý: `request_received` của các request cách nhau đúng khoảng 2.65 s dù load test chạy concurrency 5, nghĩa là server đang xử lý tuần tự.
- **Trace ID và span gây ảnh hưởng:** trace **`07876abbfc52748d1a7f2f5dd97ca08b`** (metadata `correlation_id=req-f525d3a0`) trong project `day13-k4-l3a-03005`:

  | Span | Type | Duration | Trace bình thường `82b23966c4150753bccdce7ab7416a93` (`req-906ea03a`) |
  |---|---|---|---|
  | `lab-agent-run` | agent | **2654 ms** | 152 ms |
  | `retrieval` | retriever | **2501 ms (94%)** | 1 ms |
  | `llm-generation` | generation | 151 ms | 151 ms |

  Status của mọi span đều là `DEFAULT` (không có ERROR). `llm-generation` chỉ bắt đầu sau khi `retrieval` kết thúc (11:37:13.257Z). 4 trace còn lại của incident có cùng pattern, với retrieval 2501–2515 ms. Evidence: [`evidence/14-incident-trace-spans.txt`](evidence/14-incident-trace-spans.txt) · `evidence/14-incident-trace.png`.
- **Root cause:** incident **`rag_slow`**: bước retrieval (vector store/RAG) bị treo thêm khoảng 2.5 s cho mỗi request ([`app/mock_rag.py`](../app/mock_rag.py), nhánh `STATE["rag_slow"]` → `time.sleep(2.5)`). Ba nguồn đều chỉ về cùng nguyên nhân: metric cho thấy latency tăng nhưng TTFT, token và cost không đổi; log `req-f525d3a0` có `latency_ms` 2653 nhưng `ttft_ms` 50; trace cho thấy span `retrieval` chiếm 2501/2654 ms. Yếu tố khuếch đại: `POST /chat` là `async def` nhưng gọi `agent.run()` đồng bộ ([`app/main.py`](../app/main.py)), nên retrieval chậm **chặn event loop** và các request đồng thời phải xếp hàng. Phía client, request thứ 5 phải chờ khoảng 5 × 2.65 ≈ 13 s.
- **Fix action:** tắt incident bằng `python scripts/inject_incident.py --disable` (log `incident_disabled` lúc 11:42:39Z), rồi chạy lại đúng 5 query challenge. Kết quả kiểm chứng: **P95 = 152 ms**, retrieval trở về khoảng 1 ms, 0 lỗi (các request `req-b5e1575e`, `req-bb1d9f1c`, `req-639ca0df`, `req-5816d3e0`, `req-7a5fe629`). Trên hệ thống thật, bước tương ứng là failover sang replica vector store khỏe hoặc bật cache retrieval.
- **Preventive measure:**
  1. Đặt **timeout cho retrieval** (ví dụ 500 ms) kèm fallback ("No domain document matched…"/cached docs), để RAG chậm chỉ làm giảm chất lượng chứ không làm tăng latency toàn request.
  2. Chuyển handler sang `def chat(...)` hoặc bọc bằng `run_in_threadpool`/`asyncio.to_thread` để một request chậm không chặn event loop.
  3. Thêm **alert theo span**: P95 duration của observation `retrieval` > 500 ms trong 5 phút (P2). Đồng thời hạ ngưỡng `HighLatencyP95` hoặc thêm cảnh báo sớm ở 2000 ms (`latency_threshold_ms` của challenge), vì latency server-side 2667 ms **vẫn dưới** ngưỡng 3000 ms hiện tại nên alert cũ sẽ không bắn.
  4. Log thêm `retrieval_ms` vào `response_sent` để dashboard tách được thời gian retrieval và LLM mà không cần mở trace.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** tách `retrieve()` và `FakeLLM.generate()` thành child observation (`retriever` và `generation`) dưới root `lab-agent-run`, đồng thời gắn `correlation_id` vào metadata trace. Nếu chỉ có root span, trace chỉ cho biết "request chậm 2.6 s". Khi có child span, trace ở CP3 chỉ ra ngay retrieval chiếm 94% thời gian. `correlation_id` là cầu nối giữa log và trace, giúp đi từ một log line tới đúng trace mà không phải dò theo timestamp.
- **Một lỗi/blocker đã gặp:** (1) Ở CP1, sau khi sửa code, `validate_logs.py` vẫn cho điểm thấp. (2) Ở CP3, khi lấy trace qua API bằng `Langfuse().api.trace.list()`, Langfuse Cloud trả **HTTP 410 `LEGACY_API_UNAVAILABLE_FOR_NEW_ORGANIZATION`**.
- **Cách tìm nguyên nhân và xử lý:** (1) Đọc validator thì thấy nó chấm **toàn bộ** `data/logs.jsonl`, nên các log cũ từ trước khi sửa code vẫn bị tính lỗi. Tôi lưu bản baseline sang `data/logs.baseline.jsonl`, tạo log mới rồi đo lại và đạt 100/100. Làm tương tự trước CP3 (`logs.before-cp3.jsonl`) để log incident không bị lẫn. (2) Đọc body của lỗi 410: organization tạo sau 16/09/2026 không còn dùng được endpoint `/api/public/traces`. Tôi chuyển sang `GET /api/public/v2/observations?fromStartTime=…&toStartTime=…` rồi lọc theo `metadata.correlation_id`, và lấy được duration từng span để đối chiếu với UI.
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics trả lời câu hỏi *có vấn đề không, lớn cỡ nào, từ khi nào* (P95 từ khoảng 150 ms lên 2667 ms, bắt đầu từ 11:37Z) và cho biết vấn đề không nằm ở đâu (TTFT, cost, error không đổi). Logs trả lời *request nào bị ảnh hưởng* (lọc `response_sent` theo thời gian và feature để ra `req-f525d3a0` cùng ngữ cảnh session/feature/model). Traces trả lời *chậm ở bước nào bên trong request* (span `retrieval` 2501 ms). Đi theo thứ tự này giúp thu hẹp từ toàn hệ thống xuống một request rồi xuống một span. Kết luận chỉ đáng tin khi cả ba cùng chỉ về một nguyên nhân.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** prompt version và label giúp thay đổi hành vi LLM mà không cần deploy code. Khi v2 làm giảm quality hoặc tăng token, chỉ cần chuyển label `production` về v1 là rollback xong trong khoảng 60 s (thời gian cache). Token và cost là tín hiệu riêng của LLM: một prompt dài hơn có thể không làm tăng latency nhưng lại làm vượt ngân sách, vì vậy cần panel và alert cost riêng. SLO kèm error budget biến "hệ thống ổn không" thành con số dùng để ra quyết định (dừng promote prompt/model mới khi đã tiêu > 50% budget). Challenge cũng cho thấy ngưỡng SLO phải được kiểm chứng bằng incident thật: ngưỡng 3000 ms bỏ sót mức chậm 2.6 s mà người dùng vẫn cảm nhận rõ.
- **Điều quan trọng nhất đã học:** observability chỉ hữu ích khi các tín hiệu **nối được với nhau**: cùng `correlation_id` trong log và trace, cùng khoảng thời gian trên dashboard, span được tách đủ chi tiết. Ngoài ra, cần đọc cả những metric *không* thay đổi, vì chúng loại trừ giả thuyết nhanh không kém những metric có thay đổi.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** fix ở CP3 mới dừng ở mức tắt incident. Timeout và fallback cho retrieval, việc chuyển handler sang threadpool và alert theo span `retrieval` mới là đề xuất, chưa được implement. Dashboard chỉ đo latency phía server (`latency_ms` trong log), nên không thấy thời gian xếp hàng do event loop bị chặn mà client phải chịu (lên tới khoảng 13 s). Challenge có ít request (5), nên P95 chỉ mang tính minh họa.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
