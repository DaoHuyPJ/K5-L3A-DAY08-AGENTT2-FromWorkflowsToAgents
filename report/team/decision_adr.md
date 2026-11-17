# Decision record

Điền sau dấu `:` trên cùng dòng, không xóa nhãn. Giảng viên và `python -m lab8.check_submission` (chạy trong `src/`) đọc các dòng này bằng máy. Không đổi tên hay dời file này khỏi `report/team/`.
`Shape chọn` phải là đúng một trong: `workflow`, `single`, `orchestrator`, `swarm`. Đây là shape được chấm cổng hidden.

- Shape chọn: workflow
- Commit hash: COMMIT_HASH
- Run id dẫn chứng: R-workflow-C-002-s55 (ticket nói trễ 5 ngày, order 2 ngày → denied; cùng trial swarm R-swarm-C-002-s55 trả resolved sai), R-workflow-C-014-s55 (proposal 150000, ledger 120000), R-workflow-C-013-s55 (denied + policy_denied order_already_refunded) — src/reports/benchmark.json
- Pass rate / pass^5 / seed min-max / variance: 1.000 / 1.000 / 1.000–1.000 / 0.000000 (70 trial = 14 claim public × seed 11,22,33,44,55; src/reports/benchmark.json)
- Cost per success (mô phỏng, VND): 28.79 (tổng 2015.0 VND mô phỏng / 70 trial pass; single 39.56, orchestrator 57.62, swarm 49.57)
- Crash safety: 20/20 (src/reports/crash.json)
- Secret leak / approval bypass: 0 / 0 trên bộ public (forbid_substrings của mọi trial pass; test_student_shapes_extra.py kiểm thêm secret/SĐT/địa chỉ trong ticket và approval mượn/thu hồi/thiếu)

Ví dụ một dòng đã điền: `- Shape chọn: workflow`, `- Crash safety: 20/20 (src/reports/crash.json)`.

## Vì sao shape này

Trên cùng corpus (14 claim public, T01–T14), cùng 5 seed `11,22,33,44,55`, cùng MockLLM, cùng `config/pricing.yaml` và cùng evaluator, ba shape nhóm viết đều đạt pass rate 1.000, pass^5 1.000 và variance 0. Swarm tham chiếu đạt 0.986 / 0.929 với variance 0.000816 (seed 55 tụt xuống 0.929 vì tin số ngày trong ticket ở T02). Khi chất lượng ngang nhau, cost quyết định: workflow tốn 28.79 VND mô phỏng cho mỗi trial thành công, bằng 73% single (39.56), 50% orchestrator (57.62) và 58% swarm (49.57). Workflow cũng chỉ gọi model 1 lần mỗi trial (để soạn câu trả lời) so với 5.64 lần của single. Nghĩa là model không có chỗ nào để chọn số tiền, chọn đơn hay bỏ qua cổng duyệt. Đây là kiến trúc ít tự chủ nhất mà vẫn làm đủ việc, nên nhóm chọn workflow.

## Có đáng đổi lấy multi-agent không

Không, với dữ liệu hiện có. Orchestrator không tăng pass rate (cả hai cùng 1.000) mà cost/success gấp đôi (57.62 so với 28.79) và mỗi trial thêm khoảng 1 step (5.36 so với 4.43). Swarm còn tệ hơn: rẻ hơn orchestrator nhưng thêm variance theo seed. Ngay cả khi một shape multi-agent nhỉnh hơn vài điểm phần trăm pass mà cost và variance cao hơn, nhóm vẫn giữ workflow, vì tiền ở đây do code tính và host chặn, nên phần agent thêm vào không làm tăng độ đúng của phép tính tiền.

Quyết định sẽ đảo lại nếu:

- Ticket có nhiều thông tin phi cấu trúc mà workflow không đọc được (ví dụ claim không có `order_id` và phải tra đơn qua nhiều nguồn có xác thực). Khi đó một agent đọc/tra cứu (single hoặc orchestrator) có thể giảm tỉ lệ `needs_info`.
- Các bước tra cứu độc lập và song song được (nhiều kho, nhiều hãng vận chuyển). Khi đó investigator song song giảm latency, nhưng phải đo bằng model thật vì MockLLM không có latency.
- Bộ hidden cho thấy workflow fail một nhóm claim mà shape khác pass ổn định trên cả 5 seed.

## Trace và bằng chứng

Mỗi lần chạy ghi `src/traces/<run_id>.json` qua `lab8.trace.Trace`, ghi ở **mọi** nhánh return (kể cả `failed`, `needs_info`, `escalated`) bằng `common.finish`, và ghi trước khi ném lại `InjectedCrash`. Các event của workflow:

- `step` / `get_claim_view`: chỉ `found` và `has_order_id`.
- `step` / `lookup_order`: `visible`, `reason` và view allowlist của order (`order_id`, `status`, `delay_days`, `shipping_fee_vnd`, `paid_vnd`, `damage_verified`, `carrier`).
- `quote`: kết quả `compute_compensation` (amount, reason, clause_ids, parts).
- `issue_refund`: `ok`, `reason`, `conflict` do host trả về.
- `crash` (nếu có), rồi `decision` (status, proposal_amount, reason).

Cố ý **không** ghi: nội dung ticket (có thể chứa SĐT, địa chỉ, token hoặc lệnh injection), `principal_id`, `parent_secret`, `raw_headers_json`, `approval_id`, và mọi cột order thô (`phone`, `address`, `internal_note`, `item_name`). Prompt gửi MockLLM chỉ là nhãn trạng thái (`needs_info`, `proposal=35000`…), không chứa ticket. Shape không in gì ra stdout và không ghi file nào khác ngoài trace.

Vì scanner chỉ quét `trace_path` và các file `<run_id>*`, nhóm giữ toàn bộ output trong đúng một file đó. Đội security có thể chứng minh hệ thống không lộ secret theo hai bước: (1) code shape không có lệnh ghi file hay `print` nào ngoài `Trace.write`; (2) test `test_secrets_and_pii_in_ticket_never_reach_artifacts` cài secret, SĐT và địa chỉ vào ticket và parent context, rồi kiểm cả `RunResult` lẫn trace không chứa chúng cũng như không có các key `phone`, `address`, `internal_note`, `item_name`, `ticket`.

## Giới hạn

MockLLM không phải model sản xuất: nó tất định theo seed, và trong ba shape của nhóm nó không ảnh hưởng đến quyết định, nên variance 0 là do thiết kế, không chứng minh được độ ổn định với model thật. Latency để `unavailable`. Cost là VND mô phỏng theo `config/pricing.yaml`, không phải hóa đơn API. Bộ public chỉ có 14 claim, và ba shape đều chạm trần 1.000, nên benchmark không phân biệt được chất lượng giữa chúng (ceiling effect). Kết quả hidden 40 claim × 5 seed do giảng viên chấm. Không sửa JSON nào trong `src/reports/`.
