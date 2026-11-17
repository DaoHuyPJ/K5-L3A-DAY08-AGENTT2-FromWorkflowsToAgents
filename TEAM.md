# Team

## Thông tin nhóm

- Tên nhóm: AGENTT2
- Lớp: L3A
- Repo nhóm: `K5-L3A-DAY08-AGENTT2-FromWorkflowsToAgents` (xem [SUBMISSION.md](SUBMISSION.md))
- URL repo, nhánh nộp, commit chốt: https://github.com/DaoHuyPJ/K5-L3A-DAY08-AGENTT2-FromWorkflowsToAgents, nhánh `main`, commit fcf7238

## Thành viên

| STT | Họ tên | MSSV | Email | GitHub | Vai trò |
| --: | ------ | ---- | ----- | ------ | ------- |
|   1 | Đào Quang Huy | 2A202603642 | | DaoHuyPJ | Toàn bộ (nhóm 1 người): workflow, single, orchestrator + handoff, ledger/crash, evaluation, báo cáo |

## Bảng đóng góp

`python -m lab8.check_submission` đọc bảng này bằng máy: giữ nguyên tiêu đề `## Bảng đóng góp` và các cột. Mỗi người một dòng: commit có nội dung và ít nhất một test đã thêm hoặc sửa.

| Người | Vai | Commit | Test đã thêm hoặc sửa |
| --- | --- | --- | --- |
| Đào Quang Huy | Toàn bộ: 3 shape, test, benchmark, crash, báo cáo | fcf7238 (3 shape + test + reports) | `src/tests/test_student_shapes_extra.py` (47 test: approval mượn/thu hồi/thiếu, ticket nói dối 5 seed, conflict, crash 3 điểm × 3 shape, secret/PII, handoff allowlist, step cap) |

## Cá nhân

Mỗi thành viên đồng thời tạo một báo cáo riêng trong `report/` theo dạng:

```text
report/team/MSSV_HoTen.md
```

Ví dụ: `report/team/20241234_NguyenVanAn.md`.

## 2A202603642_DaoQuangHuy

### Phần việc phụ trách

- Toàn bộ lab (nhóm 1 người): ba shape `workflow`, `single`, `orchestrator`; test bổ sung; crash suite; benchmark; ablation R1; ADR, research card, báo cáo nhóm.

### Đóng góp cụ thể

- `src/lab8/shapes/workflow.py`, `single.py`, `orchestrator.py`: cả ba qua 62/62 test student, T11/T12 xanh.
- `src/tests/test_student_shapes_extra.py`: 47 test cho các tình huống kiểu hidden.
- `src/reports/benchmark.json`, `crash.json`, `ablation_r1.json`.

### Bằng chứng

- Commit fcf7238; run id R-workflow-C-002-s55, R-workflow-C-014-s55; crash safety 20/20; chi tiết trong `report/team/2A202603642_DaoQuangHuy.md`.
