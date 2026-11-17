# Báo cáo cá nhân — MSSV_DaoQuangHuy

## 1. Thông tin thành viên

- Họ tên: Đào Quang Huy
- MSSV: MSSV
- Email:
- GitHub: DaoHuyPJ

## 2. Phần việc phụ trách

Nhóm AGENTT2 có một thành viên, nên tôi phụ trách toàn bộ: ba shape `workflow`, `single`, `orchestrator` (gồm handoff), kiểm tra ledger và crash, test bổ sung, benchmark, ablation R1, ADR, research card và báo cáo nhóm.

## 3. Đóng góp cụ thể

- **Commit chính:** fcf7238 (ba shape, test bổ sung, `src/reports/*.json`).
- **Shape A `workflow`:** các bước cố định `get_claim_view` → `lookup_order` → `compute_compensation` → `durability.issue_refund`. Model chỉ có 1 call `draft`.
- **Shape B `single`:** agent ReAct chạy qua `run_react` (max 8 step, `worker=True`). Agent tự giữ scratchpad vì `run_react` chỉ trả kết quả tool gần nhất. Code, không phải model, gọi host sau vòng lặp.
- **Shape C `orchestrator`:** `make_handoff` với `facts={}` và ba tool đọc, `run_readonly_investigators`, orchestrator tự tính quote và gọi host. Trace chỉ ghi handoff đã sanitize.
- **Test:** `src/tests/test_student_shapes_extra.py`, 47 test chạy trong cổng host.
- **Quyết định kỹ thuật:**
  - Mỗi shape tự chứa logic vì grader chỉ lấy ba file shape.
  - Luôn truyền quote đầy đủ vào host (T13, T14).
  - Không bắt `InjectedCrash`: ghi trace rồi ném lại.
  - Không ghi ticket, principal hay cột order thô vào trace.
  - Chọn `workflow` làm shape chấm hidden.

## 4. Bằng chứng

- `python -m pytest -q -m student -o addopts=`: 248 passed.
- `python -m pytest -q`: 101 passed.
- `src/reports/crash.json`: `crash_safety` 20/20.
- `src/reports/benchmark.json`: workflow 1.000 / 1.000 / variance 0 / 28.79 VND mỗi success; swarm 0.986 / 0.929.
- Run id: R-workflow-C-002-s55 (ticket nói dối → denied; swarm cùng trial R-swarm-C-002-s55 fail), R-workflow-C-014-s55 (proposal 150000, ledger 120000), R-workflow-C-013-s55 (denied, có policy_denied).
- Ablation: `src/reports/ablation_r1.json`.

## 5. Công cụ AI đã dùng

- **Claude Code (Anthropic):** đọc và tóm tắt đề bài, contract, code host; gợi ý cài đặt ba shape và bộ test bổ sung; soạn nháp ADR, research card và báo cáo.
- **Cách tôi tự kiểm tra:**
  - Chạy lại ma trận student (248 passed), cổng host (101 passed), crash suite (20/20) và `python -m lab8.check_submission`.
  - Đối chiếu từng số trong báo cáo với `src/reports/benchmark.json` và `crash.json`, không chép số từ terminal hay từ AI.
  - Đọc trace của một số run (ví dụ `src/traces/R-workflow-C-005-s11.json`) để chắc không có ticket, SĐT, địa chỉ hay secret.
  - Kiểm tra lại claim của nguồn R1 với slide tham khảo của buổi lý thuyết.

## 6. Tự đánh giá

- Ba shape qua toàn bộ test public, crash 20/20, không lộ secret trên bộ public; shape chọn `workflow` có pass rate 1.000 và cost thấp nhất.
- Điểm yếu: bộ public quá nhỏ để phân biệt chất lượng giữa ba shape (cùng chạm trần 1.000); chưa chạy tự kiểm trên `student_drop/`; variance 0 là do MockLLM tất định, chưa đo với model thật.
- Nếu có thêm thời gian: chạy `student_drop/`, thêm ablation cho single, và làm một bonus đo shape với model thật.
