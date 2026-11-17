# Báo cáo nhóm — Lab 8 LogiX-VN

Tối đa 5 trang ngoài phụ lục. Số liệu lấy từ file trong `src/reports/`, không chép tay từ terminal.

## 1. Thông tin nhóm

- Tên nhóm: AGENTT2
- Thành viên: xem `TEAM.md` (nhóm 1 người: Đào Quang Huy)
- Commit chốt (trùng `report/team/decision_adr.md`): COMMIT_HASH

## 2. Mục tiêu và cách tiếp cận

Bài toán: xử lý claim hoàn phí vận chuyển của LogiX-VN theo bốn kiến trúc có cùng chữ ký `run_claim`, rồi chọn kiến trúc ít tự chủ nhất mà vẫn đạt yêu cầu. Nguyên tắc xuyên suốt là **code quyết tiền, model chỉ soạn chữ**: số tiền do `compute_compensation` tính từ dòng order và policy hiện hành, việc ghi tiền chỉ đi qua cổng host `durability.issue_refund` (kiểm approval, trần theo đơn, idempotency), còn chữ trong ticket luôn là dữ liệu người dùng.

Nhóm làm một mình nên đi theo thứ tự mức tự chủ tăng dần:

1. Đọc contract (`docs/business_rules.md`, `docs/contracts.md`), `swarm_reference.py`, `durability.py`, `policy.py`, `runtime.py`, `handoff.py` và `metrics.trial_pass` để biết grader chấm gì.
2. Viết A `workflow` trước làm chuẩn, qua 62/62 test student.
3. Viết B `single` và C `orchestrator`, giữ nguyên phần "sau khi có quote" của workflow (nhánh deny / issue_refund / conflict), chỉ thay cách thu thập dữ kiện.
4. Viết test bổ sung cho các tình huống của bộ hidden, chạy crash suite, benchmark và ablation R1, rồi điền ADR và báo cáo.

Một ràng buộc quan trọng: grader hidden chỉ lấy ba file shape từ repo nhóm. Vì vậy mỗi file tự chứa đủ logic và chỉ import module chính thức của `lab8`, không tách helper ra file mới.

## 3. Giải pháp

Cả ba shape có chung khung kết thúc:

- Không tìm thấy claim thì trả `failed`.
- Thiếu `order_id` thì trả `needs_info`.
- Order không hiển thị với principal (không tìm thấy hoặc không phải chủ đơn) thì trả `escalated`.
- Quote = 0 thì trả `denied` với `proposal_amount=0`, không gọi host.
- Quote > 0 thì gọi `issue_refund(conn, claim_id, <quote đầy đủ>, crash_at=crash_at)`:
  - `ok` thì trả `resolved`.
  - `conflict` thì trả `failed`.
  - Bị host từ chối thì trả `denied`; `proposal_amount` vẫn là quote đầy đủ, và host tự ghi audit `policy_denied`.

Kết quả luôn được tạo qua `common.finish` để `refund_effects` và `committed_audit_count` lấy từ ledger. Shape không bắt `InjectedCrash`: nó ghi trace rồi ném lại để test resume thấy crash thật.

| Shape | Đọc gì | Ai quyết định | Model làm gì |
| --- | --- | --- | --- |
| A `workflow` | `get_claim_view` → `lookup_order` → `compute_compensation`, theo thứ tự cố định | Code Python | 1 call `draft` soạn câu trả lời |
| B `single` | Vòng `run_react` (max 8 step, `worker=True` nên tool ghi bị từ chối). Agent chọn lần lượt `get_claim_view`, `lookup_order`, `lookup_refund_history`, `compute_compensation` rồi trả `final` | Agent chỉ chọn tool đọc. Sau vòng lặp, code lấy quote từ kết quả `compute_compensation` và gọi host | 1 call mỗi step ReAct + 1 call `draft` |
| C `orchestrator` | Orchestrator đọc claim view và dựng handoff bằng `make_handoff` (`facts={}`, tool `lookup_order`, `lookup_refund_history`, `lookup_policy`). `run_readonly_investigators` chạy tool đó | Orchestrator tự tính quote từ order view của investigator và là bên duy nhất gọi host | Call `plan`, `investigate`, `draft` |

**Ranh giới code / model.** Không shape nào để model chọn số tiền, chọn đơn, sinh approval hay gọi tool ghi. Agent của single không đọc ticket để quyết định: delay luôn lấy từ cột `delay_days`, clause chỉ lấy từ policy `is_current`, mã đơn chỉ lấy từ `claims.order_id`. Nhờ đó ticket nói dối ("trễ 5 ngày", "theo SHIP-LATE-OLD", "ignore policy") không đổi được kết quả.

**Handoff.** Orchestrator không đưa ticket, `principal_id`, `parent_secret` hay header vào handoff. `facts` để rỗng vì investigator tự đọc order qua tool có kiểm phạm vi chủ đơn. `make_handoff` lọc theo allowlist, `sanitize` từ chối canary và tool ghi. Trace ghi bản handoff **đã sanitize**, không ghi parent context.

**Trace.** Chỉ ghi view allowlist (order 7 field, quote, kết quả host, tên tool của từng step ReAct). Không ghi ticket, principal, secret, header, cột order thô. Chi tiết ở mục "Trace và bằng chứng" trong `decision_adr.md`.

## 4. Kết quả

Bộ public: 14 claim × seed `11,22,33,44,55` = 70 trial mỗi shape, mỗi trial một SQLite mới (`src/reports/benchmark.json`).

| Shape | Pass rate | Pass^5 | Seed min–max | Variance | Cost/success (VND mô phỏng) | Mean / p95 steps | Model calls TB | Tool calls TB |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: | ---: |
| A workflow | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 28.79 | 4.43 / 5 | 1.00 | 2.79 |
| B single | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 39.56 | 9.86 / 11 | 5.64 | 3.64 |
| C orchestrator | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 57.62 | 5.36 / 6 | 2.93 | 5.57 |
| D swarm (tham chiếu) | 0.986 | 0.929 | 0.929–1.000 | 0.000816 | 49.57 | 2.80 / 3 | 3.00 | 4.66 |

Swarm fail đúng một trial là R-swarm-C-002-s55: ở seed 55 nó tin "trễ 5 ngày" trong ticket thay vì `delay_days = 2`, nên trả `resolved` thay vì `denied`. Ba shape nhóm viết đều trả `denied` ở trial này (ví dụ R-workflow-C-002-s55).

- Crash safety: **20/20** (`src/reports/crash.json`).
- Ma trận student: **248 passed** (`python -m pytest -q -m student -o addopts=`).
- Cổng host: **101 passed** (`python -m pytest -q`), gồm 47 test nhóm thêm trong `src/tests/test_student_shapes_extra.py`. Các test này cho cả ba shape kiểm: claim không tồn tại; approval mượn của claim khác, bị thu hồi hoặc thiếu; ticket nói dối trên cả 5 seed; đơn không tồn tại; conflict số tiền khi gọi lại; crash ở cả ba điểm rồi resume; secret và PII trong ticket không lọt vào artifact; handoff chỉ chứa allowlist; single không vượt 8 step.
- Tự kiểm trên `student_drop/`: chưa chạy vì chưa nhận bộ claim không nhãn.

Quyết định kiến trúc và lý do: xem `report/team/decision_adr.md` (chọn **workflow**). Phiếu nghiên cứu và ablation: xem `report/team/research_card.md` (R1, ablation workflow so với orchestrator).

## 5. Khó khăn và cách xử lý

- **Grader chỉ lấy 3 file shape.** Ban đầu định tách phần dùng chung (nhánh issue_refund) ra module riêng, nhưng grader hidden sẽ bỏ qua file đó và gây `ImportError`. Cách xử lý: mỗi shape tự chứa logic, chấp nhận lặp code.
- **`run_react` chỉ trả lại kết quả tool gần nhất.** Sau mỗi step, `seen` chỉ còn `last_tool` / `last_result`, nên agent mất dữ kiện các bước trước. Cách xử lý: agent của single giữ scratchpad riêng (`memory`) theo tên tool.
- **Không được trừ phần đã hoàn trước khi gửi host (T14).** Nếu shape tự trừ thì host trừ thêm lần nữa. Cách xử lý: luôn truyền quote đầy đủ; `lookup_refund_history` chỉ dùng để ghi ngữ cảnh vào trace.
- **Crash phải xảy ra thật (T12).** Bắt `InjectedCrash` sẽ làm test fail. Cách xử lý: ghi trace rồi `raise` lại.

## 6. Tổng hợp đóng góp

Chi tiết đóng góp của từng thành viên nằm trong `TEAM.md` (bảng đóng góp) và báo cáo cá nhân `report/team/MSSV_HoTen.md`. Nhóm có một thành viên, làm toàn bộ code, test và báo cáo.

## 7. Hạn chế và hướng cải thiện

- MockLLM không phải model sản xuất, latency là `unavailable`, cost là VND mô phỏng.
- Ba shape chạm trần 1.000 trên 14 claim public, nên bộ public không phân biệt được chất lượng giữa chúng. Kết luận chủ yếu dựa vào cost và mức tự chủ.
- Variance 0 là do thiết kế (model không tham gia quyết định), không chứng minh độ ổn định khi thay bằng model thật. Với model thật, agent của single có thể chọn sai tool hoặc vượt step cap; cần đo lại pass^5.
- Hướng cải thiện: chạy tự kiểm trên `student_drop/` khi có; thêm ablation cho single (tắt `lookup_refund_history` để đo chi phí của bước tra cứu thừa); nếu làm bonus, thử model thật trong `src/bonus/` với cùng evaluator.

## 8. Tài liệu tham khảo

- Đề bài và contract trong repo: `README.md`, `docs/business_rules.md`, `docs/contracts.md`, `docs/metrics.md`, `docs/architecture.md`.
- Google Research 2026, *Towards a Science of Scaling Agent Systems* (thư viện tham khảo slide 68–69), dùng cho R1 trong `research_card.md`.
- Mã tham chiếu `src/lab8/shapes/swarm_reference.py` (không copy khối `REFERENCE_WEAKNESS`).
