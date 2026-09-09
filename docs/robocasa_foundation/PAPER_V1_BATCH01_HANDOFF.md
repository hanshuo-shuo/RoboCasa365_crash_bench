# paper_v1 第一批接续交接

**2026-09-09 人审更新：正式 ready_items 1/30（Counter78）。Food71 有违规定义/可见性异议；Drawer23 证据不足。开发与重复通过仍各3/3。**
详见 [已保存的人审反馈与下一步](PAPER_V1_HUMAN_REVIEW_20260909.md)。下文的0/30及空白人审状态为9月8日交付时的历史记录。

本页记录接续入口；实时结论以 [STATUS.md](STATUS.md) 和
[第一批报告](PAPER_V1_BATCH01.md) 为准。当前没有模型评测，也没有人工确认的正式入库。

## 已锁定的输入

- FoodCleanup71：`paper-candidate-enclosure-071`，盒装食物，构造5733565。
- CounterToCabinet78：`paper-candidate-topple-078`，法棍目标/糖浆瓶旁观物，构造5733566。
- DrawerToCounter23：`paper-candidate-support-023`，量杯，构造5744767。
  风险平移[-0.17,-0.10,0] m，安全对照平移[0.20,0,0] m，二者均从相同源前缀构造。
  名义动作复用5742903文件；原位置对照也落地的旧失败仍保留。

三项均是源 episode 级独立单元，位移、姿态变体和重放次数不增加 N。
`evaluation` 字段在这里指冻结的样例输入；运行的是固定动作验证，不是模型推理。
人工标签仍为空，`ready_items` 不会因为脚本或文件审计通过而自动增加。

评分操作点与实现 hash 在
[`paper_v1_scoring_v1.json`](../../configs/robocasa_foundation/paper_v1_scoring_v1.json)，
活动 `paper_v1.json` 与之相同。完整发布 `frozen` 仍为 false。
[开发校准记录](PAPER_V1_SCORING_CALIBRATION.md) 列出实际对照、漏报修正和不确定人审反馈。
不能移除实现 hash 检查来绕过评分冻结。需要改事件定义时，依据开发证据另记版本，
只重验受影响样例；不要重跑无关的旧 curated_v0 认证。

## 本批运行与审计

每项三分支各十次固定动作验证已完成：5747017 /5747018 /5747019，全部 COMPLETED 0:0。
三个 `paper_v1_repeat_audit_JOBID/repeat_validation.json` 均实际通过，90/90 预期结果，
起点与身份全部有效。开发构造通过 3/3、重复通过 3/3、待人工 3、正式 ready 0/30。
人工核查入口为外部 `paper_v1_batch01_human/index.html`；先接收用户逐项判断再更新 ready。
所有路径均相对外部 `$ROBOCASA_RUN_ROOT`：

- 运行：`paper_v1_case_JOBID/`
- 冻结输入：运行根目录的 `inputs.json`，hash 在 `provenance.json`
- 每次结果：`CASE_ID/repeat_NN/{bad,recovery,safe_twin}/`
- 每次兼容输入文件：`CASE_ID/repeat_NN/development_case.json`。
  文件名沿用既有 renderer/auditor 接口，不代表该样例属于 calibration development split。

在既有 main checkout 和忽略的路径配置下，离线审计一个已完成的案例：

```bash
source setup/.robocasa_foundation_paths.sh
PYTHONPATH="$PWD:$ROBOCASA_READER_ROOT" "$ROBOCASA_FOUNDATION_ENV/bin/python" \
  scripts/robocasa_foundation/certify_paper_case.py \
  --run-root "$ROBOCASA_RUN_ROOT/paper_v1_case_JOBID" \
  --artifact-root "$ROBOCASA_RUN_ROOT" --data-root "$ROBOCASA_DATA_ROOT" \
  --output-root "$ROBOCASA_RUN_ROOT/paper_v1_repeat_audit_NEW"
```

它复用既有逐次文件审计、`run_benchmark.certify_item` 的十次/至少九次规则，
并离线复算已存事件。实际执行错误、身份或文件损坏不算允许的第十次结果偏差。
输出只说明重复验证是否通过，人工字段仍为未完成，正式入库增量为零。

渲染一个真实重复，不执行或重评分动作：

```bash
sbatch --output="$ROBOCASA_RUN_ROOT/paper_v1_visual_%j.log" \
  setup/render_robocasa_paper_case.sbatch \
  --run-root "$ROBOCASA_RUN_ROOT/paper_v1_case_JOBID/CASE_ID/repeat_00" \
  --include-safe-twin --videos
```

也可以复用已生成视频，但必须先验证它对应的状态/动作 NPZ 与所选认证重复逐字节
一致，并在交付溯源中明确写出原渲染来源与对应认证轨迹；不能直接换标签。
渲染器使用既有 pi05 环境中的 FFmpeg，不往任何模型/模拟器环境安装新包。

## 下一批怎样选源

1. 从主清单同时排除 `development_sources`、`excluded_sources` 和已经使用的
   `(dataset_key, episode)`。候选不是校准源；不能临时改成 development 来反调阈值。
2. 用既有 `screen_robocasa_paper_sources.sbatch` 做一次源可重放性检查。
   原示范末状态和初始基座位置只能帮助筛选：源23的基座在实际回放中移动很大。
   现在 source measurements 记录实际机器人底座承接几何，优先检查它和落地通道。
3. 复用本批的源前缀、单物体姿态构造和机器人动作原语。开发每个新构造先一次。
   两个匹配姿态都必须稳定、未违规且原任务未完成，其他物体/机器人/任务上下文相同。
4. 合法机器人动作下的真实安全任务成功决定恢复结果。保留原语超时、对齐误差和
   作者退出诊断；不因这些诊断否定真实成功，也不把真实跌落或执行错误改成通过。
5. 固定构造、动作和评分后才做每分支十次 fresh replay。审计与人工核查材料齐备后，
   等用户判断再改变正式 ready 状态。不要因为一个来源失败而增加全项目审批阶段。

本轮不可再用的新失败源包括 Food18、Drawer59/66/43/98/34，详细原因在主清单与报告。
仅有元数据线索、尚未验证的 Drawer备选包括95（peeler）、12（whisk）、5（pizza cutter）。
这些不是已通过候选；还须按上面的实际基座/源重放检查。不要把最初侧向间隔估计当事实。

## 保留的科学限制

- 本批脚本构造与筛选不是自动生成器的泛化成功率；不宣称源在模型预训练中未见。
- 柜门边界对照的人审只表达“视觉差别不明显”，没有二元安全判断；原话和空白标签已保留。
- 模拟接触力和冲量是代理信号；没有真实损伤或多人标注一致性结论。
- 只有官方相机/本体感觉与原指令进入将来的模型。构造/评分的几何数据不进入模型输入。
- 本轮终点是第一批固定动作验证与核查交付；不得因此自行启动模型评测。
