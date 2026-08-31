# 我的明确判断

**不要继续把“LIBERO 里不断加入 wall / glass / staleness / unstable placement”扩成 CrashBench 的主体。** 现有 LIBERO 工作应当冻结为一个很有价值的机制性 pilot：它已经证明了三件事——自然策略会沿着危险路径继续执行，风险可以从隐藏状态中被识别，外部 monitor/controller 可以避免碰撞；真正没有解决的是“如何在保持原任务的前提下恢复并完成”。

重新开始后，最合理的主线是：

> **RoboCasa365 作为任务与场景层，robosuite/MuJoCo 作为状态和物理层，SafeManip/OopsieVerse 作为安全谓词层，MimicGen 与现有演示作为技能分段和 witness 脚手架；CrashBench 只新增“经认证的 pre-crash branch point”这一关键层。**

换句话说，CrashBench 不再以“我人为设计了多少种危险”为核心，而以：

> **在同一个尚未发生事故的状态中，危险继续执行与安全完成任务两条轨迹都被实际验证存在。**

作为最小评测单元。

这不是重新从零开始。你前面的弯路实际上帮你找到了一条比最初 proposal 更清楚的论文边界。

---

# 一、为什么最初的 proposal 到现在需要改写

最初 proposal 在思想上没有错，尤其是“每个状态都必须有 recovery witness”这一点非常重要。但以 **2026 年 8 月 31 日**的文献格局看，单纯做“失败注入＋恢复数据＋多个模型评测”已经不够新了。

FRBench 已有 23,453 个模拟 episode、46 个双臂任务和 6,392 条经过验证的多步恢复轨迹；其协议明确分成 nominal execution、error projection 和 recovery execution。FailSafe 则在 ManiSkill 中注入 translation、rotation 和 no-op failure，并收集了约 13.1 万个 failure-action pair，再系统验证 recovery action。

安全 benchmark 也已经迅速变得拥挤：SafeManip 在 50 个 RoboCasa365 任务上定义了八类时序安全性质；OopsieVerse 在 RoboCasa 和 BEHAVIOR 中加入机械、热和液体损伤，并提供 32 个 household task；LIBERO-Safety 已有 40 个任务和 19,664 条严格无碰撞示范；ManiGuard 则包含 200 个 locked base task、1,000 个 ID/OOD scenario 和 8,000 条 safe-success demonstration。

因此，原 proposal 中这些部分已经不能单独构成足够强的 novelty：

- 50 个手工 recovery witness；
- wall、glass、slip、drop、joint limit 等七类 failure taxonomy；
- “VLAs 缺乏 recovery data”这一宽泛结论；
- 常规 error injection 后再测能否恢复；
- 再做一个通用 safety predicate library。

CrashBench 真正还能占住的位置，是：

> **不是 failure-state recovery，而是 pre-violation branch-choice recovery：事故尚未发生，任务仍然可完成，但策略必须主动离开当前错误演化方向。**

FRBench 的 recovery 是在经过 error projection、已经形成 verified adverse state 后开始；FailSafe 主要围绕 motion-stage perturbation 与 corrective action；SafeManip 和 ManiGuard 主要评估完整 rollout 是否违反安全性质。CrashBench 应当专门研究更窄、更严格的问题：**在不可逆损害发生之前，模型能不能识别并选择一条经验证的任务保持恢复分支。** 

---

# 二、把 benchmark 的基本单位从“场景”改成“认证分叉点”

我建议把项目正式改写成：

## CrashBench: Certified Recoverable Branch Points for VLA Manipulation

每个 benchmark item 不再只是一个 XML、一份 state pickle 和一个 crash predicate，而是：

\[
b=(\mathcal T,\;s^\*,\;H^\*,\;\tau_{\text{bad}},\;\tau_{\text{rec}},\;\phi_C,\;\phi_G,\;s^+)
\]

其中：

- \(\mathcal T\)：原始自然任务和语言指令；
- \(s^\*\)：事故尚未发生的分叉状态；
- \(H^\*\)：标准化的观测历史、控制器上下文和待执行 action-chunk 状态；
- \(\tau_{\text{bad}}\)：从该状态出发，确实会触发 crash predicate 的危险 witness；
- \(\tau_{\text{rec}}\)：从完全相同的状态出发，避免事故并完成原任务的 recovery witness；
- \(\phi_C\)：物理安全或损伤谓词；
- \(\phi_G\)：原任务成功谓词；
- \(s^+\)：matched safe twin，即只修改关键危险变量后的安全对照状态。

一个样本只有满足以下条件才进入 benchmark：

1. **起点尚未违规**：\(\phi_C(s^\*)=0\)。
2. **危险分支可复现**：重复执行 \(\tau_{\text{bad}}\)，能够稳定触发事故。
3. **恢复分支完成原任务**：\(\tau_{\text{rec}}\) 不仅安全，而且满足 \(\phi_G=1\)。
4. **状态本身稳定**：零动作保持一小段时间后不自行坍塌、滑落或产生事故。
5. **模型具备名义能力**：至少在 paired safe twin 上能完成任务，否则不能把失败归因于 recovery。
6. **重启上下文完整**：物理状态、控制器状态、观测历史、随机数和 action buffer 都有明确协议。

这会形成一个非常清楚的区别：

| 评测对象 | 问题 |
|---|---|
| 普通任务 benchmark | 模型能否从正常初始状态完成任务 |
| safety benchmark | rollout 是否违反某条安全规则 |
| failure-recovery benchmark | 已经出现 adverse state 后能否修复 |
| **CrashBench** | **事故尚未发生且恢复仍可行时，模型能否选择任务保持的安全分支** |

“同状态双 witness”比“人为加一个危险物体”更接近可检验的科学定义。

---

# 三、框架系统比较

下面评分是针对你这个项目的适配度，不是对框架总体质量的评价。5 分表示特别适合做 certified recoverable branch point。

| 框架 | 任务自然性 | 状态重启/分叉 | failure 与 witness authoring | VLA 与 baseline 生态 | 2026 年论文空间 | 判断 |
|---|---:|---:|---:|---:|---:|---|
| **LIBERO** | 3 | 4 | 2 | 5 | 2 | 适合作为 controlled pilot，不宜再做主 benchmark。它原本面向 lifelong learning，已有 4 个 task suite、130 个任务；现在 LIBERO-Safety 又已覆盖大规模 obstacle/safety 扩展。 |
| **robosuite** | 2 | 5 | 4 | 3 | 3 | 最好的底层 substrate 之一，但不适合作为论文的任务身份。它原生支持记录环境 state、直接恢复 state replay、teleoperation、sensor delay/corruption。 |
| **RoboCasa365** | **5** | 4 | **4** | **5** | **4** | **最推荐的主框架。**任务自然、fixture 丰富、已有演示和强模型，只需增加 branch-point 层。 |
| **ManiSkill** | 3 | **5** | **5** | 4 | 2 | 工程上最容易，但 FailSafe 已经高度覆盖“阶段扰动＋验证 recovery”。更适合方法开发 sandbox，而非重新做 recovery benchmark。 |
| **Isaac Lab** | 4 | 3 | **5** | 4 | 3 | 高保真、GPU 并行、规划和传感器强，但对 MVP 太重；官方文档也明确提示 `env.reset` 后 physics replay 可能非确定性。 |
| **MimicGen** | — | 继承底层 | **5** | — | 4 | 不是 simulator，而是数据和技能分段层。应当与 RoboCasa/robosuite 组合，而不是单独选择。 |
| **CALVIN** | 3 | 3 | 2 | 3 | 2 | 长时语言任务清楚，但物理与 failure-authoring 较弱，现代 safety/recovery 基础设施不占优势。其核心是 34 个技能及五指令序列评测。 |
| **SimplerEnv** | 4 | 2 | 2 | **5** | 2 | 很适合后续做 sim-real behavior transfer validation，不适合做精确 branch-state 和 witness authoring 的主平台。 |

一个简化结论是：

> **如果只比较“最快做出 planner oracle”，ManiSkill 最强；如果比较“最有说服力的 benchmark paper”，RoboCasa365 最合适。**

---

# 四、为什么最终选 RoboCasa365，而不是继续 LIBERO 或转 ManiSkill

## 1. 它同时具备任务图、自然场景、演示数据和现代 baseline

RoboCasa365 有 365 个 everyday task、2,500 个 kitchen environment，其中 145 个任务不需要 mobile manipulation。它建立在 robosuite/MuJoCo 上，既保留了你熟悉的物理和状态接口，又提供了大量真实语义的 drawer、cabinet、microwave、counter、sink、appliance 等 fixture。

它的数据发布中已经包含用于 replay 的 MuJoCo raw state、MJCF model XML 和环境/controller metadata；复合任务还提供逐帧 subtask index、atomic skill name、pick/place/navigate stage 和自然语言指令。

这意味着你不需要重新定义整套 task mechanics。你可以在已有 task graph 的技能边界上定义：

> “上一个 subgoal 看似结束，但其后置条件没有充分满足；继续下一个技能会导致 crash。”

这比“在机械臂路径中随机放一面墙”自然得多。

## 2. 已有足够强的模型，benchmark 不会被 nominal competence 拖死

RoboCasa365 已有公开 leaderboard，覆盖 50 个目标任务和多个 evaluation split，包含 π0、π0.5、GR00T、Diffusion Policy 等模型家族，并提供相应提交和 checkpoint 信息。

因此主表不必完全依赖你当前的 OpenVLA。更合理的是：

- 用 RoboCasa 官方适配过的 π0.5 和 GR00T 作为主要 VLA；
- 用 Diffusion Policy 或其他非 VLA policy 作为控制组；
- OpenVLA 保留为你最熟悉的 representation/probe 模型，适配成功后再进入主表。

这样可以避免再次出现“benchmark 做好了，但基础模型连正常任务都不会做”的问题。

## 3. 现有 safety 工作反而能替你节省工作

SafeManip 已经定义了 object containment、release stability、mechanism recovery、enclosure access 等时序谓词；OopsieVerse 已经提供了基于接触力等物理信号计算机械损伤的思路。你不应该与它们竞争“谁的安全 taxonomy 更全”，而应直接把这些 predicate 当作基础设施。

CrashBench 新增的是：

- 从自然 rollout 中定位事故前状态；
- 构造同状态的 unsafe/recovery 双 witness；
- 定义恢复 lead time；
- 区分 safe abort 与 task-preserving recovery；
- 发布可精确重启的 branchpoint package。

这正是“只修改最关键的一层”。

---

# 五、最应该先做的 failure mechanism

## 首选：**未充分完成放置后，继续关闭 fixture**

也可以命名为：

> **Latent Obstruction at a Skill Transition**  
> 技能转换处的潜在阻塞

一个典型任务是：

> “把杯子放入抽屉，然后关闭抽屉。”

### 分叉状态

- 杯子已经释放并静止；
- 杯子部分位于抽屉内部，但仍伸出抽屉关闭路径；
- 机械臂已经开始撤离或准备关闭；
- 当前没有碰撞、夹压或损伤；
- 原任务仍然完全可以完成。

### 危险 witness

继续执行原来的 `close drawer` subskill：

- 抽屉撞上杯子；
- 产生较大接触力、夹压或损伤；
- 抽屉卡住，或者物体被推出/打翻；
- 触发 crash predicate。

### Recovery witness

- 停止关闭；
- 必要时重新打开；
- 回撤；
- 重新抓取或推送物体；
- 确认物体完全进入 enclosure；
- 回撤机械臂；
- 关闭抽屉；
- 完成原始任务。

### Matched safe twin

场景、机器人姿态、语言指令和视觉背景全部相同，只把杯子移动到完全位于抽屉内部的位置。

SafeManip 已经覆盖“closing hits obstacle 后需要恢复”“物体完全进入 enclosure 后才能释放”等机制，因此你可以复用它的谓词，不必把这个 failure category 宣称为新的安全定义。你的贡献是把这些规则变成 **事故前、同状态、双轨迹可验证的 recovery benchmark item**。

## 为什么它比 wall、glass、grasp slip 更适合第一版

第一，它是**任务自身产生的障碍**，不是人为放入无关物体。杯子之所以成为危险物，是因为前一个技能没有正确完成，而下一个技能仍被启动。

第二，它测试的是**跨阶段因果推理**。从当前画面看，机械臂可能暂时没有碰撞；模型必须意识到“现在关闭会出事”。

第三，它有真实的 task-preserving recovery。停住只是 safe abort；真正恢复需要回退、修正上一步、再继续任务。

第四，它可以在物体已经释放和稳定后取 snapshot，避开你之前遇到的 held-object、gripper latch、controller target 没有一起恢复的问题。

第五，它与 Cold Diffusion / known-good-state routing 的联系最自然：恢复策略可以把状态送回“物体已完全放入、机械臂已撤离”这个 known-good anchor，再继续成功轨迹。

第一批只做 **drawer 和 cabinet**。等状态重启与 witness pipeline 稳定后，再加入 microwave 或其他 appliance。不要一开始又扩成七类事故。

---

# 六、不要手工逐个设计场景，而要从自然失败中“挖掘分叉点”

最合理的 authoring pipeline 不是：

> 想一个事故 → 加一个物体 → 写一个 predicate → 再想办法恢复。

而是：

## 1. 从现有任务和模型 rollout 中挖掘真实错误

在 RoboCasa 的正常任务上运行已经适配的 VLA，利用 SafeManip/OopsieVerse 风格的 privileged monitor 找到：

- 第一次 unsafe transition；
- 第一次接触或损伤；
- 第一次明显违反 subtask postcondition 的时刻。

优先保留模型自然产生的 incomplete placement、premature next-skill 和 unsafe closure。

## 2. 从事故时刻向前回溯

设事故发生在 \(t_C\)。向前搜索一组候选 \(t^\*<t_C\)，要求：

- 此时尚未违规；
- 状态可以稳定暂停；
- 原策略或记录下来的 continuation 仍然会造成事故；
- 从此处存在任务完成的 recovery。

这才是自然的 pre-crash state。

## 3. 只在自然样本不足时做最小 counterfactual perturbation

这种 perturbation 不应是“加一面墙”，而应当来自模型真实误差分布，例如：

- 沿物体插入方向减少 2–5 厘米；
- 增加小幅 release pose offset；
- 提前结束 placement subskill；
- 提前启动 fixture-closing skill。

并在数据中明确标记：

- `policy_induced`
- `counterfactual_from_policy_error`
- `scripted_stress_case`

主结果分别报告，避免 benchmark 被批评为只针对某个模型的特定错误。

## 4. recovery witness 不要依赖通用 RRT* 单独完成

RRT 类 planner 适合 free-space connector，却不擅长接触丰富的重抓取、推送和 fixture 操作。更合适的是一个 hybrid witness：

1. 用 privileged task state 确定上一处 known-good subtask anchor；
2. 用 typed skill skeleton 执行 `retract → reopen → regrasp/push → replace → retract`；
3. 局部 free-space motion 使用 motion planner；
4. 接触操作使用 scripted servo 或少量 teleoperation；
5. 接回原成功 demonstration 的 suffix；
6. 完整 replay，验证安全和任务成功。

RoboCasa 已有大量人类演示、MimicGen 数据和 subtask annotations，这会显著降低 witness 的制作成本。

---

# 七、状态恢复协议必须重新定义

你之前遇到的 active-grasp snapshot 问题说明：**MuJoCo 的 qpos/qvel 不是完整的 benchmark state。**

CrashBench 发布的 state bundle 至少应包括：

- MuJoCo physics state：qpos、qvel、act、ctrl、mocap、fixture state；
- controller target、integrator、reference pose；
- gripper command、desired aperture 和 latch 状态；
- task/subtask bookkeeping；
- simulator、task、sensor 和 domain-randomization RNG；
- observation delay/filter buffer；
- 相机配置；
- 最近若干 observation；
- previous action 和尚未执行完的 action chunk；
- policy sampling seed。

但我更建议采用：

> **canonical prefix 是真值，raw snapshot 是加速缓存。**

也就是每个 branchpoint 同时保存：

1. 从标准初始状态到 \(s^\*\) 的 deterministic prefix；
2. branchpoint full-state bundle；
3. replay 后的 state hash 和 predicate hash。

RoboCasa 数据本身已经发布了 raw MuJoCo states、模型 XML 和 replay metadata，但 CrashBench 仍需补上 controller 与 policy context，才能达到 branch-level reproducibility。

评测可分成两个协议：

### State-recovery protocol

清空模型历史，提供统一长度的当前观测上下文，取消未执行 action chunk。测试“从这个状态本身能否恢复”。

### Self-recovery protocol

保留导致当前状态的观测历史、模型历史和 pending action chunk。测试“模型能否从自己的漂移中纠正”。

最小版本先把 **state-recovery** 做扎实；self-recovery 是后续更强的分析。否则不同模型的 history length 和 action chunk 会让 benchmark 很难公平。

---

# 八、T-1 / T-5 / T-20 应改成物理时间到事故

原 proposal 的 T-1、T-5、T-20 在只测一个固定控制器时有意义，但跨 π0.5、GR00T、OpenVLA-OFT 等模型后，step 不再可比：

- action chunk 长度不同；
- policy inference rate 不同；
- simulator control frequency与 executed-action frequency 不同；
- 一个“step”可能对应一个 delta action，也可能对应八个连续 action。

建议把 horizon 改为：

> **Certified Time-to-Violation under the locked bad witness**

即从 \(s^\*\) 出发执行固定 \(\tau_{\text{bad}}\)，到第一次触发 crash predicate 的模拟物理时间。

可以在 pilot 后锁定三个区间，例如：

- near：约 0.25–0.5 秒；
- medium：约 0.75–1.5 秒；
- far：约 2–4 秒。

具体边界应由实际轨迹分布决定，并在主评测前锁定。论文主图仍然可以是：

> task-preserving recovery rate versus certified lead time

但其横轴应当是秒，而不是某个模型自己的 action step。

---

# 九、最重要的指标应当是 competence-conditioned recovery

安全 benchmark 最容易被“什么都不做”钻空子。ManiGuard 和 SafeManip 的结果也显示，安全率与任务成功必须拆开看；一个模型可能安全只是因为从未真正参与任务。

因此 CrashBench 的 headline metric 不应只是 crash rate，而应是：

\[
\mathrm{CCR}
=
\frac{
\sum_j
\mathbf 1[
S_j^{+}=1
\land
R_j^{-}=1
]
}{
\sum_j
\mathbf 1[
S_j^{+}=1
]
}
\]

其中：

- \(S_j^+=1\)：模型在 matched safe twin 上能完成任务；
- \(R_j^-=1\)：同一模型在危险 branchpoint 上既不 crash，又完成原任务。

可以命名为：

> **Competence-Conditioned Recovery Rate**

这回答的是：

> 在已经证明该模型会做这个任务的样本上，它遇到 recoverable pre-crash state 后还能否完成？

同时报告：

- crash rate；
- recovery + task success；
- safe abort；
- unsafe task success；
- peak force / accumulated damage；
- recovery latency；
- backtracking cost；
- path length overhead；
- recovery rate versus lead time。

这样 stop shield 会获得低 crash rate，但 CCR 接近零；真正的 recovery policy 才能获得高 CCR。

---

# 十、最小可发表版本应该长什么样

## A. Go/no-go pilot

先只做：

- 2 个 fixture 类型：drawer、cabinet；
- 2–3 个原始 RoboCasa task template；
- 20–30 个 certified branchpoint；
- 每个 branchpoint 有 bad witness、recovery witness、safe twin；
- 1 个强 VLA、1 个非 VLA policy、1 个 scripted oracle。

建议采用以下接受门槛：

| 项目 | 建议门槛 |
|---|---:|
| 起始状态无安全违规 | 100% |
| bad witness 重复触发事故 | ≥95% |
| recovery witness 完成原任务 | ≥90% |
| branchpoint 重启一致率 | ≥95% |
| 至少一个模型在 safe twin 上成功 | ≥60% |
| 基础模型危险分支不是全部 no-op | 必须满足 |
| recovery 不能仅靠停止完成 | 必须满足 |

达不到这些门槛时，不应扩任务数，而应先修 benchmark protocol。

## B. 最小具备完整论文说服力的版本

| 维度 | 最小范围 |
|---|---|
| 核心机制 | 1 个统一机制：incomplete placement → unsafe fixture transition |
| Fixture family | drawer、cabinet、microwave 或 appliance door |
| 原始任务 | 6–10 个 RoboCasa atomic/short-composite task |
| Branchpoint | 120–180 个 |
| Lead time | 3 个物理时间区间 |
| Scene/object variation | 未见 kitchen、未见物体尺寸、未见 fixture geometry |
| Policy | 至少 2 个现代 VLA＋1 个非 VLA policy |
| Witness | 每项 bad＋recovery 双 witness |
| 对照 | matched safe twin |
| 来源 | 多 source-policy failure mining，并保留 source-policy holdout |
| Baseline | vanilla、stop/retract shield、geometric filter、recovery prompt、recovery-trained/routing method |
| 主要分析 | recovery-vs-lead-time、safe abort trade-off、risk representation-vs-action |

最小主结果应该能够支持以下四句话：

1. 模型在 paired safe twin 上能够完成任务，却在 pre-crash branch state 中频繁选择危险继续执行。
2. 增加事故前 lead time 并不会自动转化为更高的 task-preserving recovery。
3. stop/shield 很容易降低 crash，但主要把 crash 转化成 safe noncompletion。
4. recovery demonstrations 或 known-good-state routing 能够提高 CCR，但仍存在明显的 unseen-scene / unseen-object generalization gap。

## C. 主会版本的安全线

仅有一个 failure mechanism 和约 150 个状态，即使 protocol 很干净，也可能被认为范围偏窄。要提高到 ICLR/CoRL 主会更有说服力的形态，建议在第一机制稳定后增加一个共享同一抽象的第二 operator，而不是再扩七类无关事故：

1. **Incomplete postcondition before next skill**  
   放置没有充分完成，却启动关闭、插入或搬运下一技能。

2. **Unstable release before downstream action**  
   物体已释放但处于边缘、倾斜或未稳定状态，继续下一动作将导致跌落或碰撞。

两者都属于：

> **task-graph edge 上的 recoverable transition failure**

这样论文仍是一个统一问题，而不是七个各自写 mechanics 的小 benchmark。主会版本最好再加入一个实际 recovery method，例如 Cold Diffusion/known-good-state routing，并用少量真实 drawer/cabinet 案例验证趋势。

---

# 十一、原 proposal 哪些保留，哪些删除

## 应当保留

- 每个样本必须有 feasibility witness；
- crash、recovery+task、safe abort、severity 分开报告；
- OOD-but-not-crash control；
- held-out object/scene generalization；
- hidden-state risk probe；
- classical shield baseline；
- recovery-finetuned 与 known-good-state routing；
- 少量 real-robot validation 作为强化证据。

## 应当修改

| 原设计 | 新设计 |
|---|---|
| 50 个手工 scenario × 7 类事故 | 120–180 个从自然任务中挖掘的 certified branchpoint |
| wall/glass 等 asset-oriented category | task-graph transition failure |
| T-1/T-5/T-20 action steps | physical time-to-violation |
| 单一 state pickle | prefix＋full restart context＋state hash |
| witness 只证明“不撞” | witness 必须“不撞且完成原任务” |
| 所有模型直接平均 | 先通过 matched safe twin 做 competence conditioning |
| 先接入五种模型 | 先把一个强模型和一个非 VLA 的协议做对 |
| self-report AUC 作为 killer figure | branchpoint certification 和 CCR 才是核心；probe 是解释性分析 |
| MJX 优先 | 先用可复现的 MuJoCo CPU pipeline；吞吐不是当前主要瓶颈 |
| real robot 早期进入 | simulator protocol 稳定后再做小规模验证 |

---

# 十二、现有 LIBERO 工作怎么保留

现有结果不应丢掉，但要重新定位。

它可以成为论文中的 **controlled mechanism study**：

1. **因果性验证**：on-path obstacle 确实导致 crash，而 matched off-path control 不会。
2. **表征—行动脱节**：hidden state 可以识别风险，但原策略没有把风险转换为恢复行为。
3. **安全—完成脱节**：monitor/controller intervention 可以避免碰撞，却经常不能完成原任务。
4. **offline—online gap**：离线排序或 recovery option 看似有效，fresh sequential execution 未必真正选择它。
5. **activation steering negative result**：可线性解码风险，不等于可以沿该方向直接控制行为。

这些实验正好解释为什么新 benchmark 必须同时包含：

- bad continuation；
- task-completing recovery；
- online branch choice；
- matched safe twin；
- post-intervention distribution。

你已有的 predicate API、state logger、probe、intervention harness、counterfactual routing 和 outcome decomposition 都可以迁移到 RoboCasa/robosuite。真正需要换掉的只是“人工墙作为任务世界”。

---

# 最终建议

**主框架：** RoboCasa365。  
**底层：** robosuite + MuJoCo。  
**安全谓词：** 优先复用 SafeManip，机械损伤可借鉴 OopsieVerse。  
**技能与 witness：** RoboCasa demonstration/subtask annotation + MimicGen + typed skill recovery。  
**状态来源：** 多个 VLA 自然 rollout 中挖掘，必要时做符合真实误差分布的最小 counterfactual perturbation。  
**第一 failure mechanism：** 物体未完全放入 enclosure，却准备关闭 drawer/cabinet。  
**benchmark 单位：** 同一 pre-crash state 上的 bad witness、task-preserving recovery witness 和 matched safe twin。  
**核心指标：** competence-conditioned recovery rate，而不是单独 crash rate。  
**现有 LIBERO wall 项目：** 冻结为 controlled pilot 和机制分析，不再扩成主 benchmark。  
**ManiSkill：** 保留为快速方法实验环境，不作为主 benchmark，因为 FailSafe 的重叠过强。  
**Isaac Lab/ManiGuard：** 适合后续跨模拟器验证；不建议当前立即迁移为 MVP 主线。

最适合现在这项工作的论文主张，不再是：

> “VLAs 在人为障碍前会撞墙。”

而是：

> **“即使事故尚未发生、原任务仍可完成，并且同一状态存在经过验证的恢复路径，当前 VLA 仍经常无法选择任务保持的安全分支；风险识别、停止保护与真正恢复是三个不同能力。”**

这比最初的 wall benchmark 更自然，也更能把你已经做出的 risk probe、controller intervention、exact-state recovery 和 offline→online negative result 统一成一个完整研究故事。
