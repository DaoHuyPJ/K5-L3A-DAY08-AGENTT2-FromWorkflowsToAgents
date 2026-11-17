# Research card

File này nằm cố định ở `report/team/research_card.md`; `python -m lab8.check_submission` đọc cột "Nhóm điền" bằng máy.

Phần này nối tiếp phần mini research ở buổi lý thuyết (slide 62–63). Chọn **một** câu R1–R4, điền 6 dòng, rồi biến nó thành **một ablation** chạy được trong lab: giữ nguyên model (MockLLM), tool, seed, corpus và giá, chỉ thay đổi một biến.

| Câu | Nguồn (thư viện tham khảo, slide 68–69) | Câu hỏi gợi ý cho lab |
| --- | --- | --- |
| R1 · Scaling | Google Research 2026, *Towards a Science of Scaling Agent Systems* | Task claims chủ yếu tuần tự hay song song được? Dự đoán thêm investigator sẽ làm pass rate và cost/success thay đổi thế nào. |
| R2 · Failure taxonomy | MAST, NeurIPS 2025, *Why Do Multi-Agent LLM Systems Fail?* | Các trial fail của swarm (seed 55) thuộc nhóm nào: lỗi giao việc, lệch mục tiêu, hay lỗi kiểm chứng? |
| R3 · Architecture choices | AgentArch, AACL 2026 | Nếu đổi topology mà giữ nguyên mọi thứ khác, biến nào phải cố định để kết luận còn đúng? |
| R4 · Evaluation confounders | EMNLP 2026, *Rethinking Evaluation of MAS Efficiency* | Làm sao chứng minh chênh lệch giữa A/B/C/D là do topology, không phải do prompt, tool hay seed? |

## Phiếu của nhóm

Điền vào cột cuối. Không xóa hai cột đầu.

| Field | Hướng dẫn | Nhóm điền |
| --- | --- | --- |
| CÂU | R1 / R2 / R3 / R4 | R1 · Scaling |
| SOURCE | Paper/blog, năm, URL, loại bằng chứng (benchmark, production report, blog kinh nghiệm) | Google Research 2026, *Towards a Science of Scaling Agent Systems* (thư viện tham khảo slide 68–69 của buổi lý thuyết). Loại bằng chứng: benchmark có kiểm soát, so nhiều topology agent trên nhiều nhóm task |
| CLAIM | Một kết luận gốc của nguồn. Không viết rộng hơn phạm vi paper | Lợi ích của việc thêm agent / phối hợp nhiều agent phụ thuộc vào cấu trúc task: task tách song song được thì có lợi, còn task tuần tự chặt thì chi phí phối hợp lấn át lợi ích, hiệu năng có thể giảm |
| BOUNDARY | Model / dataset / setup giới hạn kết luận đó | Kết luận rút từ model LLM thật trên các benchmark agent của paper, không phải từ task claims có tiền do code tính. Trong lab: MockLLM tất định, 14 claim public, quyết định tiền nằm ở code và host chứ không ở model, nên chỉ kiểm được vế "cost tăng" chứ không kiểm được vế "chất lượng giảm" |
| HYPOTHESIS | Nếu đổi shape A→B (hoặc bật/tắt một thành phần), metric X sẽ đổi theo hướng nào, khoảng bao nhiêu | Task claims tuần tự chặt (claim → order → quote → host gate, bước sau cần kết quả bước trước). Đổi A `workflow` → C `orchestrator` (thêm một investigator read-only và một handoff) sẽ không tăng pass rate (giữ 1.000), còn cost/success tăng khoảng +50% đến +100% và mean steps tăng khoảng +1 |
| METHOD | Biến giữ cố định: model, tools, seed, corpus, giá, evaluator. Biến duy nhất được thay đổi: … | Giữ cố định: MockLLM, bộ tool `lab8.tools`, seed `11,22,33,44,55`, corpus `data/public_claims.jsonl` (14 claim), `config/pricing.yaml`, evaluator `lab8.metrics.trial_pass`, host `durability.issue_refund`, quote bằng `compute_compensation` ở cả hai shape. Biến duy nhất được thay đổi: topology, có hay không có lớp investigator read-only + handoff (workflow so với orchestrator) |
| FAILURE / METRIC | Một lỗi dự kiến và cách đo nó: pass rate, pass^5, variance, cost/success, leak, bypass | Lỗi dự kiến: chi phí phối hợp (thêm model call `plan`/`investigate`, thêm tool call qua handoff) không mang lại thêm độ đúng. Đo bằng cost/success và mean model calls, kèm pass rate và pass^5 để chắc chất lượng không đổi. Đồng thời kiểm leak = 0 qua handoff (handoff chỉ chứa field allowlist) |

## Kết quả ablation

- Lệnh đã chạy (copy nguyên văn): `python -m lab8.benchmark --shapes workflow,orchestrator --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out reports/ablation_r1.json`
- Run id / file report: `src/reports/ablation_r1.json` (trùng số với `src/reports/benchmark.json`); ví dụ R-workflow-C-014-s55 và R-orchestrator-C-014-s55
- Kết quả so với hypothesis (đúng / sai / không kết luận được), kèm số liệu: **Đúng.** Pass rate 1.000 → 1.000, pass^5 1.000 → 1.000, variance 0 → 0 (không đổi). Cost/success 28.79 → 57.62 VND mô phỏng (+100%, ở cận trên của dự đoán). Mean steps 4.43 → 5.36 (+0.93). Mean model calls 1.00 → 2.93, mean tool calls 2.79 → 5.57. Thêm investigator chỉ làm tăng chi phí phối hợp, không tăng độ đúng trên task tuần tự này
- Giới hạn: MockLLM không phải model sản xuất, latency là `unavailable`. Cả hai shape chạm trần 1.000 trên bộ public (ceiling effect), nên ablation không phát hiện được trường hợp chất lượng giảm như paper mô tả. Cost là VND mô phỏng, phụ thuộc cách mỗi shape đếm model call. Chỉ có 14 claim.
