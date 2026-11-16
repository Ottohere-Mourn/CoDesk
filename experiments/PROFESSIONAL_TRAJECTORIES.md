# 专业软件任务的真实操作轨迹

`professional_trajectories.py` 将 2026-10-30 构建的 Blender、FreeCAD、QGIS
任务交给截图驱动的模型执行。它直接使用 Responses API 的函数工具循环，
不依赖嵌套 Codex CLI 或其容器内沙箱。模型、推理等级沿用传入的凭据配置。

每个 solo 任务使用一个新 Docker 桌面，只挂载对应的初始文件副本到
`/workspace`。桌面没有网络，模型没有 shell 或文件读取工具。API 凭据、
评分器和参考答案不挂载到执行容器。宿主机通过固定命令执行截图和键鼠操作。

默认 `--access gui` 限制正常界面、快捷键和应用表达式字段，禁止代码控制台；
这个限制由工具表面和提示共同实现，仍需审核动作与截图。可显式选择
`--access app-console` 进行另一个允许应用内 Python 控制台的条件。
该条件应独立报告，不应与纯 GUI 成绩混合。

在 VM10 的 `/data/yuke/paraGUI/CoDesk` 内运行：

```bash
/data/yuke/paraGUI/.test-venv/bin/python -u -m experiments.professional_trajectories \
  --dataset /data/yuke/paraGUI/authoring/professional-20261030T162043Z/work \
  --credentials /data/yuke/paraGUI/authoring/professional-20261030T162043Z/private/api.json \
  --out /data/yuke/paraGUI/trajectories/<新批次> \
  --tasks p1a p3a p2a --max-actions 180 --timeout 1200

python3 -m experiments.summarize_professional_trajectories \
  /data/yuke/paraGUI/trajectories/<新批次>
```

运行目录必须不存在；重试使用新目录，保留失败尝试。API 的 429 冷却错误
等待至少 30 秒后重试，最多 6 次，并受该任务的墙钟预算限制。仅重试模型
请求，不重放桌面操作。其他已有桌面和源素材不受影响。

每个动作记录操作参数、前后窗口焦点、前后截图和时间。模型可以一次请求
最多 12 个顺序动作；每个动作都有存档截图，但模型只看到批次最后一张。
后续请求保留最近 3 张图及全部文字/工具记录，原始请求使用相对图片路径
保存，可从同目录截图还原。

产物停止修改后复制到独立评估容器，使用上一批评分器读取原生状态和导出。
`result.json` 分别保存模型停止状态、自述、独立分数、用量和输入/输出哈希。
`completed` 仅表示模型完成作答。失败、超时和预算耗尽的轨迹同样保留。

汇总脚本产生 `REPORT.md`、`trajectory-summary.json`、`index.html`；每个任务的
`trajectory.html` 支持本地逐步浏览。完整性检查核对动作编号、截图、产物哈希，
并确认记录的每个动作确实来自对应模型响应。它不替代对画面和任务完成度的人工审核。

原批次评分器是试验评分器，部分检查依赖具体序列化方式，例如 FreeCAD
图纸要求四个 `<circle>` 标签。这里保留原评分口径，并单独列出未通过项。
目前尚未把这批专业任务注册进 OSWorld，也未测量并发干扰。

API 格式依据：[函数调用](https://developers.openai.com/api/docs/guides/function-calling/)
及[图像输入](https://developers.openai.com/api/docs/guides/images-vision/)。
