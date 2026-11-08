

----

喵。这份 OS 路线总体合理，我赞成以它作为系统开发的主线。 它比之前单纯讨论 Linux、Theseus、微内核的路线更具体：以 Rust 建立系统资源管理模型，以 Linux 提供第一阶段的隔离和执行能力，再逐步加强内核约束。

但我建议先修正几个地方。尤其是第二阶段的内核改造、第三阶段的 Rust 编译器扩展，以及 NPU 调度和机器人控制之间的边界。

我会保留你的三阶段 OS 方向，同时重新规划其余部分，最终形成一套完整的系统方案。

# 一、先评审你的 OS 设计

## 1. 硬件选择是合理的

复旦微官方给出的 FMQL30TAI 芯片规格包括：

- 4 核处理器，最高 1 GHz。
    
- 1 MB 二级缓存，256 KB 片上存储。
    
- 8 路 DMA 通道。
    
- 1 个 ZG330 iCore NPU。
    
- INT8：8 TOPS。
    
- FP16：4 TFLOPS。
    
- TF32：2 TFLOPS。
    
- 支持 INT8、FP16、BF16、TF32。
    
- FPGA PL 具有 125K 逻辑资源、78,600 LUT 和 400 个 DSP。
    
    复旦微 · 可编程逻辑器件+1
    

[第十届集创赛复旦微电子企业命题开启报名-电子发烧友网](https://images.openai.com/static-rsc-4/M10Zh_6UVjEtM6Ybmmn4tzDVntzdgQQvAs4uzXsSzo-1uJNi8Lhj6DO-Z3-eS4joT4TkYE-iymcDjSVglT2QGfOmQPVqYpeOtgHPRtoiWAGAe4UygV4kziwYDSWijEfdznu_619_icLf3Y7a-TNfOtbMHhXdPXvAV2bQRI9KmZw?purpose=inline)

[elecfans.com](https://www.elecfans.com/d/7648924.html?utm_source=chatgpt.com)

你的 PS + NPU + PL 三类资源管理方向是正确的。

不过要增加三个约束：

第一，NPU 算力不能等同于 CPU 算力。

8 TOPS 是 INT8 推理能力指标，并不意味着机器人控制、MoveIt 规划或一般 Rust 代码也能得到相应加速。

第二，统一 DDR 不等于完全不需要同步。

官方介绍了 PS、NPU、FPGA 共享统一 DDR 和零拷贝协作能力。

复旦微 · 可编程逻辑器件

但仍然需要管理：

- Buffer 生命周期。
    
- CPU 与设备的访问所有权。
    
- Cache coherency。
    
- Memory barrier。
    
- DMA 映射和解除映射。
    
- NPU 完成通知与同步 Fence。
    

第三，不要先假定具有 IOMMU。

芯片有 DMA 通道，不代表就具有能够保护任意设备 DMA 访问范围的 IOMMU/SMMU。

需要从芯片 TRM、BSP、Device Tree 和驱动中确认。没有硬件 DMA 隔离能力时，不能声称只靠 Rust 类型就实现了 DMA 内存隔离。

## 2. 三阶段 OS 路线需要调整

你现在的规划：

1. Linux 上实现 Rust 资源管理层。
    
2. 改造内核。
    
3. 扩展 Rust 编译器。
    

我认可大方向，但建议改成：

|阶段|核心内容|目标|
|---|---|---|
|OS-1|Rust Hosted System|验证系统模型、资源管理和组件隔离|
|OS-2|Linux Enforcement Extension|把确实无法由用户态强制执行的约束下沉到内核|
|OS-3|Rust Static Assurance|将可静态证明的安全规则转化为编译期约束|
|OS-4（可选）|Native Kernel Research|研究 Linux 不适合承担的基础机制是否值得自研|

其中 OS-4 不代表你必须自研内核，而是保留这条可能性。

更重要的是，OS-3 不应该成为 OS-2 的必然后继阶段。

编译器扩展是独立的语言与静态分析研究方向。你可以在 OS-1 期间就开始研究 Typestate、Capability 类型和静态检查。

## 3. Capability Manager 不等于内核 Capability

这是第一阶段最需要注意的安全问题。

Linux 上的 Rust Capability Manager 可以管理：

- 谁能够请求某项资源。
    
- 哪个组件拥有什么资源权限。
    
- 哪些权限可以撤销。
    
- 哪些组件能访问特定设备。
    
- 哪些资源由谁持有。
    

但是，用户态管理器本身不能阻止一个拥有任意系统调用权限的进程绕过它。

必须由 Linux 内核的权限机制实施最终限制。

第一阶段可以组合使用：

|Linux 机制|负责的事情|
|---|---|
|Process / MMU|地址空间隔离|
|cgroups v2|CPU、内存、I/O 等资源限制|
|Namespace|资源视图与命名空间隔离|
|seccomp|系统调用过滤|
|LSM / AppArmor|内核访问控制|
|Landlock|用户态可配置的文件系统访问限制|
|Linux Capabilities|细粒度的传统特权权限|

这些都有现成的内核实现，不需要你重新发明。

The Linux Kernel documentation+3

我建议把 Resource Manager 定义为：

> 负责资源策略、准入、所有权、预算分配和生命周期；由内核负责最终强制执行。

例如：

```
Rust Resource Manager
        |
        | Resource Grant
        v
Linux Enforcement Backend
        |
        +-- cgroups
        +-- seccomp
        +-- LSM
        +-- namespaces
        |
        v
Kernel Enforcement
```

这才是真正意义上的 Kernel-enforced Resource Management。

## 4. Rust 编译器扩展要重新排序

你的第三阶段思路值得研究，但有些属性并不能单纯依靠类型系统实现。

|目标|Rust 能否表达|建议实现方式|
|---|---|---|
|资源访问权限|可以部分表达|Capability 类型、私有构造器|
|设备生命周期|可以|Typestate|
|DMA Buffer 所有权|可以部分表达|Ownership + RAII + 状态机|
|地址空间标记|可以描述|Newtype / 类型化句柄|
|运行时撤销|不能仅靠 Lifetime|Revocation Handle / Generation|
|真实内存访问隔离|不能只靠类型|MMU / 内核强制|
|CPU 预算限制|不能只靠类型|内核计量与限制|
|WCET 保证|一般 Rust 类型系统无法提供|静态分析与实时系统分析|

尤其是 `Revocable references`：

Rust Lifetime 描述的是编译期生命周期，不是一个运行时权限可以被随时撤销的保证。可以设计可撤销 Capability Handle，但需要运行时机制。

我建议编译期开发顺序是：

1. Newtype、Trait、Lifetime、Typestate。
    
2. Capability Wrapper 和安全 API。
    
3. Proc Macro 与代码生成。
    
4. Clippy / 静态分析规则。
    
5. MIR 数据流分析。
    
6. 有明确必要时，再修改 rustc 类型检查或借用检查机制。
    

Rust 的 Procedural Macro 主要操作语法 Token Stream；要分析程序的实际类型关系、控制流和数据流，需要进入更深层的编译器分析接口。Rustc 官方开发文档确实提供 MIR 数据流分析框架，但使用编译器内部 API 会带来工具链维护成本。

The Rust Reference+2

所以不建议一开始就 Fork rustc。

# 二、重新确定整个系统的总体架构

我建议最终项目不要只有 OS 和 Inference 两大部分，还应该正式增加 Robotics、Home Automation、Safety 五个领域。

Application & Domain Layer

Smart Home

自动化、语音、设备控制

Robotics

运动规划、感知、控制

AI Services

ASR、NLU、LLM、视觉

Multimedia

音视频、传感器数据流

System Runtime Layer — Rust

Resource Manager · Capability Manager · Component Manager · Scheduler · Supervisor · IPC

Inference Runtime

CPU / NPU / PL / Tensor / DMA

Device Runtime

Home Devices / Robot Hardware / Drivers

Platform & Kernel Layer

Linux Backend → Linux Kernel Extensions → 可选 Native Kernel

FMQL30TAI Hardware

PS / ZG330 NPU / FPGA PL / DDR / DMA / Peripherals

Independent Physical Safety

Robot E-stop · Motor Protection · Limit Switch · Safety Controller

物理安全路径独立于普通系统调用链，不应依赖主机操作系统正常运行。

这里不是一个要求所有服务都使用 Rust 或者 ROS 2 的架构。

我的语言分工建议是：

|语言|主要职责|
|---|---|
|Rust|OS 资源管理、推理管理器、设备监督、系统服务|
|C/C++|ROS 2 生态、控制器、厂商运行时适配|
|HDL|FPGA PL 自定义逻辑|
|Python|算法开发、仿真脚本、模型转换、实验工具|
|厂商代码|ICraft Runtime、驱动等|

Rust 是系统的主要开发语言，不是所有现有生态都必须被重写成 Rust。

# 三、完整开发大纲

下面按照正式项目架构来组织。我建议将它作为未来的总体开发 Wiki 大纲。

## 第一部分：系统总体设计

### 1. 系统目标

构建以 Rust 为主要系统语言的异构智能家居与机器人操作系统。

目标能力：

- 多组件运行与资源管理。
    
- 组件故障隔离和恢复。
    
- 统一权限与 Capability 管理。
    
- CPU/NPU/FPGA 异构计算。
    
- ONNX 模型管理和部署。
    
- 智能家居自动化。
    
- 机器人感知、规划和控制。
    
- 物理设备生命周期管理。
    
- 实时任务和资源预算管理。
    
- 运行时安全与编译期安全协作。
    

### 2. 设计原则

1. Rust 负责系统核心和安全 API。
    
2. Linux 初期提供成熟的内核能力。
    
3. 不重复实现 Linux 已有机制。
    
4. 不重复实现 ICraft 已有 NPU 编译与执行能力。
    
5. 机器人领域优先利用 ROS 2 生态。
    
6. 物理安全不能依赖普通软件故障恢复。
    
7. 统一资源合同，但允许不同资源使用不同调度策略。
    
8. 组件隔离粒度依据故障后果和信任边界决定。
    
9. 所有关键优化都要有 Benchmark。
    
10. 架构允许更换 Linux、ROS 2、推理引擎和自研组件。
    

### 3. 硬件抽象

明确管理以下资源：

|计算/硬件单元|负责内容|
|---|---|
|PS CPU|系统服务、调度、预处理、CPU 推理|
|ZG330 NPU|AI 算子及神经网络推理|
|FPGA PL|自定义硬算子、数据流处理、硬件接口|
|DDR|共享模型和数据 Buffer|
|DMA|PS 与各硬件单元之间的数据搬运|
|外设|UART、SPI、I²C、CAN、Ethernet、GPIO 等|
|独立安全设备|物理执行器保护，按设备配置|

需要补充板级信息：PS DDR 容量、PL 侧 DDR 是否独立、实际 DMA 路由、缓存一致性策略、IOMMU/SMMU 是否存在、NPU 驱动版本。不能只根据芯片宣传页推导这些板级细节。

# 四、OS：Rust 资源管理与安全系统

保留你的三阶段结构，但展开成可实施模块。

## OS-1：Linux Hosted Rust System

最先开发

### 1. Resource Manager

```
resource-manager/
├── cpu
├── memory
├── storage
├── network
├── npu
├── fpga
├── dma
└── device
```

负责：

- 资源注册和查询。
    
- 资源申请。
    
- 资源分配。
    
- 资源释放。
    
- 使用量统计。
    
- 资源冲突检测。
    
- 资源准入控制。
    
- 资源配额。
    
- 资源过载处理。
    

注意资源类型不应全部用一个简单的数字额度表示。

例如：

- CPU 是时间预算。
    
- 内存是容量限制。
    
- NPU 是执行队列、模型会话和设备资源。
    
- DMA Buffer 是带有设备访问权的内存对象。
    
- 机械臂是具有独占控制权的物理设备 Lease。
    

### 2. Capability Manager

```
capability-manager/
├── capability
├── object
├── permission
├── delegation
├── revocation
└── policy
```

主要负责：

- 对象能力注册。
    
- 权限检查。
    
- Capability 委托。
    
- 权限撤销。
    
- 设备操作授权。
    
- 组件权限清单。
    
- 资源所有权验证。
    

未来可以让 Capability 与内核对象直接关联。

例如：

```
Capability<RobotArm, MotionCommand>
Capability<Camera, ReadFrame>
Capability<NpuDevice, Inference>
Capability<ResourceManager, AllocateBudget>
```

这只是类型化接口设计；第一阶段不能把它误当成内核已经实现了真正的对象级 Capability。

### 3. Component Manager

负责：

- 组件注册。
    
- 组件依赖。
    
- 组件启动。
    
- 组件停止。
    
- 组件替换。
    
- 组件配置。
    
- 组件身份与权限。
    
- 组件资源声明。
    

建议每个组件提供 Manifest：

```
component:
  id: inference.npu
  version: 0.1.0

  execution:
    isolation: process

  permissions:
    - npu.execute
    - model.read

  resources:
    cpu: limited
    memory: 128MiB
    npu_sessions: 1

  dependencies:
    - resource-manager
    - inference-core
```

真正的资源大小和硬性限制应该在部署阶段配置和校验。

### 4. Lifecycle Manager

负责统一管理：

- Created
    
- Configured
    
- Ready
    
- Active
    
- Suspended
    
- Failed
    
- Recovering
    
- Terminated
    

组件状态机不能和业务设备状态机混为一谈。

例如，一个机械臂可以处于 `FAULTED`，但管理它的 Robot Service 仍然处于 `RUNNING`。

### 5. IPC

分成两个路径：

|通信类型|第一阶段实现|
|---|---|
|控制消息|Unix Domain Socket|
|高频数据|Shared Memory|
|大型设备 Buffer|dma-buf（驱动支持时）|
|通知|eventfd / event mechanism|
|远程领域通信|ROS 2 DDS 或明确的 Gateway Protocol|

不建议所有 IPC 都走 JSON 或 HTTP。

### 6. Resource Ownership

这里要定义 Resource Lease。

例如：

```
ResourceLease
├── resource_id
├── owner_component
├── granted_permissions
├── expiry
├── revocation_state
└── resource_handle
```

需要实现：

- 独占资源分配。
    
- 多读者共享。
    
- 写入者互斥。
    
- 超时释放。
    
- 进程退出释放。
    
- 强制撤销。
    
- 失效后禁止继续使用。
    

特别重要：不要只依赖 Rust `Drop` 释放物理资源。进程可能崩溃或被强制终止；必须由内核句柄、Resource Manager 和 Supervisor 协作回收。

### 7. Recovery Manager / Supervisor

负责：

- 健康检查。
    
- 心跳。
    
- 运行时资源监控。
    
- 组件崩溃检测。
    
- 超时检测。
    
- 自动重启。
    
- 故障隔离。
    
- 依赖故障传播处理。
    
- 恢复后的状态重新验证。
    

不要将所有故障都直接处理为重启。NPU 模型会话、设备控制权和机器人运动状态需要独立恢复流程。

## OS-2：Linux Kernel Enforcement Extension

这一阶段的原则是：先配置、再集成、最后修改内核。

建议按下面的优先级：

|模块|具体工作|
|---|---|
|权限控制|LSM、Linux Capabilities、设备节点权限|
|进程隔离|MMU、Namespace|
|资源限制|cgroups v2|
|系统调用限制|seccomp|
|文件访问限制|Landlock / AppArmor|
|DMA|Linux DMA API|
|共享 Buffer|dma-buf / fence（驱动支持时）|
|NPU 访问|厂商驱动及用户态 Runtime|
|中断管理|Linux IRQ 子系统|
|实时性|PREEMPT_RT、优先级和中断线程|
|CPU 预算|调度策略、cgroups、准入策略|

Linux PREEMPT_RT 通过线程化中断、可抢占的锁实现和优先级继承改善实时响应。

The Linux Kernel documentation+1

但你的系统真正需要的可能是部分功能，而不是全部改造。

我建议给每一个内核修改项增加一个门槛：

```
现有 Linux 能否实现？
        |
        +-- 能：使用现有机制
        |
        +-- 不能：
              |
              v
是否有实际安全/性能问题？
              |
              +-- 没有：不修改
              |
              +-- 有：设计最小内核扩展
```

特别是 DMA 与 NPU，先检查厂商驱动是否正确使用 Linux DMA API，再决定是否改造。DMA API 负责 CPU 虚拟地址、物理地址和设备 DMA 地址之间的映射管理；有无 IOMMU 会影响实际隔离能力。

GitHub+2

## OS-3：Rust Static Assurance

建议拆成四个子项目：

A. Resource Type System

- CPU Budget Type。
    
- Memory Region Type。
    
- DMA Buffer Type。
    
- Device Ownership Type。
    
- Capability Handle Type。
    

B. Component Type System

- Component Identity。
    
- Component Lifecycle。
    
- Trust Level。
    
- Execution Domain。
    
- Dependency Constraint。
    

C. Static Analysis

- 禁止绕过安全 API。
    
- 禁止不安全的 Buffer 转移。
    
- 检查 DMA 所有权状态。
    
- 检查资源访问授权。
    
- 检查组件生命周期约束。
    

D. Compiler Integration

- Proc Macro。
    
- Clippy 检查。
    
- MIR 数据流检查。
    
- 之后才评估 rustc 修改。
    

## OS-4：未来内核演进研究

保留三条可选方案：

|方向|主要研究目标|
|---|---|
|Linux 增强型系统|继续使用 Linux，只扩展缺失机制|
|seL4 / L4|Capability、地址空间和调度预算强制隔离|
|Theseus 式系统|语言级组件隔离、单地址空间和低开销组件通信|

不要现在决定最终是哪一个。

# 五、Inference：Rust 异构推理系统

你的推理层本身设计得不错，我只建议将它进一步整理成六个子系统。

## 1. Inference API

统一应用接口：

```
InferenceManager
├── load_model()
├── unload_model()
├── create_session()
├── execute()
├── cancel()
├── inspect()
└── report_usage()
```

应用只需要说明：

- 模型。
    
- 输入。
    
- 执行需求。
    
- Deadline。
    
- 是否允许 CPU fallback。
    

不直接暴露 ICraft API。

## 2. Rust Workspace

我建议这样组织：

```
inference/
├── inference-api/
├── inference-core/
├── model-registry/
├── model-manifest/
├── tensor-manager/
├── memory-pool/
│
├── backend-cpu/
│   ├── tract/
│   └── ort/
│
├── backend-fpai/
│   ├── icraft-api/
│   ├── model-loader/
│   ├── device-manager/
│   └── runtime-session/
│
├── fpai-ffi/
│
├── backend-pl/
│   ├── accelerator-api/
│   └── bitstream-manager/
│
├── inference-scheduler/
├── inference-benchmark/
└── inference-validation/
```

有一个值得更正的技术点：

现在 Sonos 的 Rust 推理引擎对外主要使用 `tract` 门面 crate，官方介绍其 CPU Runtime 支持 ARM 架构。建议优先评估它，而不必直接绑定内部 `tract-onnx` 等底层 crate。

GitHub+1

`ort` 则是 Rust 对原生 ONNX Runtime 的绑定，不是纯 Rust 推理引擎。它适合作为一个性能和算子覆盖率对照 Backend，但需要处理原生库与目标板 ABI 的适配。

Rust+1

因此第一阶段：

- tract：纯 Rust CPU 后端。
    
- ORT：可选原生 CPU 后端。
    
- ICraft：专有 NPU 后端。
    

三个都用同一套测试模型比较，不急着固定唯一 CPU 后端。

## 3. ICraft Backend

这一层建议集中处理所有 C++ FFI。

```
Rust Inference Core
        |
        v
FPGAI Backend
        |
        v
C ABI Wrapper
        |
        v
C++ ICraft Runtime
        |
        v
ZG330 NPU
```

复旦微官方明确说明 ICraft 包含：

- Icraft-compiler：模型解析、优化、量化、映射和代码生成。
    
- Icraft-runtime：模型加载、NPU 执行和推理任务管理。
    
- Icraft-show：推理调试和性能分析。
    

官方还提到 Runtime 能管理同一芯片上的多个模型，并支持无 OS 的 BareMetal 部署。

复旦微 · 可编程逻辑器件

因此，你的 Rust Inference Manager 不应该重复开发 NPU 内部调度。

Rust 负责：

- 系统级任务准入。
    
- 模型生命周期。
    
- CPU/NPU Backend 选择。
    
- 内存与权限管理。
    
- 故障处理。
    
- 与 OS Resource Manager 的交互。
    

ICraft 负责：

- NPU 内部执行管理。
    
- 模型部署。
    
- NPU 任务执行。
    

FFI 方面，我建议使用独立 C ABI 包装层，不要让 Rust 直接依赖 C++ ABI。

C ABI 包装层负责：

- Opaque Handle。
    
- 固定宽度类型。
    
- 错误码。
    
- Buffer 传递。
    
- 回调。
    
- `catch (...)` 截获 C++ 异常。
    
- 关闭时资源回收。
    

不要让 C++ 异常穿越 C ABI。

## 4. Tensor / DMA Buffer Manager

这是非常值得你自研的部分。

```
TensorManager
├── Tensor
├── DeviceBuffer
├── SharedBuffer
├── DmaBuffer
├── BufferAllocator
├── BufferMapper
├── CacheSync
├── Fence
└── OwnershipTracker
```

除了 Shape、DType、Layout，还必须区分：

- CPU 可访问性。
    
- NPU 可访问性。
    
- PL 可访问性。
    
- DMA 可访问性。
    
- 缓存一致性。
    
- Buffer 当前所有者。
    
- Buffer 是否允许被设备异步访问。
    

可以利用 Rust typestate 表达 Buffer 所有权转移：

```
CpuOwned
   |
   v
SubmittedToNpu
   |
   v
NpuOwned
   |
   v
NpuCompleted
   |
   v
CpuOwned
```

真实设备访问和同步仍需后端实现保证，类型只能提供一层静态约束。

## 5. CPU / NPU 动态调度

你提出的两阶段方式是正确的。

### 第一阶段：整模型 Backend 选择

优先完成：

```
               ONNX Model
                    |
                    v
              Model Analysis
                    |
          +---------+---------+
          |                   |
        CPU                 NPU
          |                   |
       tract / ORT          ICraft
          |                   |
          +---------+---------+
                    |
                    v
               Result
```

选择因素：

1. 算子支持。
    
2. 模型 Shape。
    
3. 数据精度。
    
4. 输入尺寸。
    
5. 数据当前所在位置。
    
6. CPU 计算时间。
    
7. NPU 排队时间。
    
8. 数据搬运开销。
    
9. 内存压力。
    
10. Deadline。
    

我建议增加一套 Model Profile：每个模型记录在当前硬件上的实际加载时间、推理时间、内存占用、精度损失和数据迁移成本。

Auto 不是简单根据 CPU 利用率选择 NPU。

还要设计 Backend 切换的滞后策略，避免负载轻微波动时频繁切换。

### 第二阶段：CPU / NPU 子图执行

这里我会保留你的规划，但将它放到后面。

必须先确认 ICraft 是否提供足以让外部系统控制子图执行、共享中间 Tensor 和同步的接口。公开资料能确认它有模型编译和 Runtime，并不意味着任意 ONNX Graph 都能在 CPU、NPU 之间任意切割。

复旦微 · 可编程逻辑器件

所以顺序应是：

1. 手动划分若干连续子图。
    
2. 验证 ICraft 能否编译对应子图。
    
3. 验证中间 Tensor 的格式和 Buffer 共享。
    
4. 测量跨设备搬运和同步成本。
    
5. 最后实现自动 Graph Partitioner。
    

不需要一开始就写 ONNX Compiler。

## 6. FP32 / INT8 / FP16 / BF16 / TF32

建议按照以下次序：

|精度|优先级|主要用途|
|---|---|---|
|FP32|基准参考|CPU 结果与数值对照|
|FP16|高|NPU 初期部署|
|INT8|高|性能、功耗和内存优化|
|BF16|中|特定网络与算子支持验证|
|TF32|中|需要验证对应算子和 Runtime 的支持|

芯片层面的精度支持不意味着所有 ICraft 版本、所有算子或所有模型都能使用全部精度。应当形成：

```
Operator × DType × Shape × Compiler Version × Runtime Version
```

的能力矩阵。

# 六、Robotics：独立机器人系统

这个部分是原方案缺失较多、需要新增的重点。

我建议将其作为和 Inference 平级的独立项目。

## 1. Robotics Runtime

```
robotics/
├── robot-description/
├── robot-model/
├── robot-state/
├── robot-hardware/
├── robot-controller/
├── robot-planning/
├── robot-perception/
├── robot-safety/
├── robot-gateway/
└── robot-simulation/
```

各自职责：

|模块|职责|
|---|---|
|Robot Description|URDF / Xacro / SRDF|
|Robot Model|关节、连杆、动力学和约束|
|Robot State|关节状态、传感器反馈|
|Robot Hardware|电机、驱动器和编码器|
|Controller|周期控制、轨迹跟踪|
|Planning|逆运动学、路径和碰撞规划|
|Perception|目标识别、点云、视觉定位|
|Safety|安全检查和运动约束|
|Gateway|与 HA4FPAI 业务系统交互|
|Simulation|仿真、标定和故障注入|

## 2. ROS 2 生态

建议优先评估：

|组件|用途|采用建议|
|---|---|---|
|ROS 2|机器人通信与节点运行时|使用|
|ros2_control|硬件抽象与控制器管理|使用|
|MoveIt 2|机械臂运动规划|使用|
|Gazebo|仿真和 ROS 集成|第一套仿真平台|
|MuJoCo|动力学和接触控制研究|作为备选/补充|
|Nav2|移动机器人导航|有移动底盘后再接入|
|micro-ROS|MCU 端接入 ROS 2|后续评估|

`ros2_control` 已有 System、Sensor、Actuator 等硬件组件类型和 Resource Manager；Mock Components 还能模拟命令与状态交互，测试控制器、驱动链路和 MoveIt 集成。

ROS2_Control: Rolling Nov 2026 documentation+2

ROS 2 不负责你的 OS Resource Manager，也不替代整个设备控制系统。 它属于机器人领域运行时。

## 3. Sim-to-Real

建议单独建立一条研发链路：

```
Robot Specification
       |
       v
URDF / Xacro / SRDF
       |
       v
Dynamics & Sensor Model
       |
       v
Gazebo / MuJoCo
       |
       v
Controller Validation
       |
       v
System Identification
       |
       v
Parameter Calibration
       |
       v
Hardware-in-the-Loop
       |
       v
Real Robot
```

需要开发的内容：

- 动力学模型。
    
- 执行器模型。
    
- 摩擦和回差模型。
    
- 传感器噪声模型。
    
- 控制周期与通信延迟模型。
    
- 系统辨识。
    
- 标定。
    
- Domain Randomization。
    
- HIL / SIL。
    
- 实机轨迹误差比较。
    
- 故障注入。
    

Gazebo 和 `gz_ros2_control` 能够连接仿真与控制器；Mock Components 能测试接口流水线，但它不是高精度真实动力学仿真。

ROS2_Control: Rolling Nov 2026 documentation+1

## 4. Robot Safety

这一部分不能只由 Rust 的普通 Resource Manager 实现。

需要独立建模：

```
Robot Safety
├── Safety State
├── Emergency Stop
├── Joint Limits
├── Workspace Limits
├── Velocity Limits
├── Torque / Current Limits
├── Communication Watchdog
├── Collision Constraints
└── Safe Recovery
```

架构必须区分：

- HA4FPAI 请求机器人做什么。
    
- 规划器决定如何运动。
    
- 控制器决定如何跟踪运动。
    
- 安全控制器决定什么运动是允许的。
    

尤其是急停、制动和电机保护，不应该依赖 Linux、LLM 或普通 ROS 2 节点仍然正常运行。

# 七、Smart Home：智能家居领域

这里不建议直接把 ROS 2 当作整个 Home Domain 的中间件。

可以保留现在的一些业务模型，但不要求保留现有 Python 实现。

建议结构：

```
home/
├── automation/
├── devices/
├── entities/
├── state/
├── events/
├── commands/
├── schedules/
├── scenes/
├── users/
├── permissions/
└── protocol-adapters/
```

协议适配器按具体设备选择：

- Matter。
    
- MQTT。
    
- Modbus。
    
- CAN。
    
- UART / SPI / I²C。
    
- GPIO。
    
- HTTP 等网络设备接口。
    

不要强制所有设备都有统一的 `turn_on()` 和 `turn_off()`。门锁、摄像头、机械臂、环境传感器的能力模型应当不同。

## 业务流程模型

建议将这几种对象分开：

|对象|表达内容|
|---|---|
|Event|发生了什么|
|Command|请求设备执行什么|
|Durable Task|哪个业务任务需要持久化和恢复|
|Work Item|哪个工作已经就绪、等待执行|
|Execution Context|实际运行该工作的执行实体|
|Resource Lease|暂时持有哪些资源|

例如：

```
用户说：让机械臂拿起杯子
       |
       v
Intent / NLU
       |
       v
Command Gateway
       |
       v
Robot Goal
       |
       v
Planning & Execution
       |
       v
Result Event
       |
       v
Home State Update
```

注意：机器人控制循环不能等待普通业务任务队列分配 Worker 后再执行。

# 八、统一调度与资源管理

这是你此前一直在探索的方向，我建议正式作为单独的 System Runtime 项目。

不要把整个系统仅仅看作 CPU Scheduler。

至少有五种不同的调度对象：

|调度对象|所在层级|
|---|---|
|Durable Task|业务持久化层|
|Work Item|应用运行时|
|OS Thread / TCB|CPU 调度层|
|NPU Job / Session|ICraft Runtime|
|Robot Control Cycle|机器人实时控制层|

其中可以共享统一的资源合同格式：

```
execution_contract:
  criticality: high

  timing:
    period_ns: 10000000
    deadline_ns: 8000000
    budget_ns: 2000000

  resources:
    cpu: 1
    memory_bytes: 67108864
    npu: false
    device_lease:
      - robot.arm.main

  overload:
    policy: reject
```

但不同后端有不同的执行语义。

例如：

- CPU：Linux Scheduler。
    
- NPU：ICraft Runtime。
    
- FPGA：专用硬件 Pipeline。
    
- Robot Controller：周期性实时执行。
    
- 机械臂：设备独占 Lease。
    

System Scheduler 管理跨领域的策略、准入和资源分配；实际 CPU 调度由 Linux 内核承担，NPU 内部由 ICraft 管理，机器人控制器按实时周期运行。

这样才是真正意义上的统一资源调度体系，而不是一条全局 Ready Queue。

# 九、系统安全与故障恢复

建议独立成立一个项目，而不是散落在 Resource Manager 和 Device Manager 里。

## 1. 安全模型

至少有五类隔离：

|隔离类型|要解决什么问题|
|---|---|
|Memory Isolation|一个组件不能访问其他组件内存|
|Authority Isolation|一个组件不能操作未授权设备|
|Temporal Isolation|一个组件不能无限占用执行时间|
|Resource Isolation|一个组件不能耗尽其他组件的资源|
|Fault Isolation|一个组件故障不能无限扩散|

## 2. 故障类型

分别研究：

- Process crash。
    
- Memory exhaustion。
    
- Infinite loop。
    
- Deadlock。
    
- NPU hang。
    
- DMA failure。
    
- FPGA fault。
    
- Device disconnect。
    
- Stale sensor data。
    
- Robot control deadline miss。
    

不同故障需要不同响应。

例如 NPU 推理服务重启后可以重新加载模型；机械臂控制通信丢失时，不能简单重启驱动后继续执行上一条运动命令。

## 3. Recovery

增加：

- Component Recovery。
    
- Device Recovery。
    
- Resource Recovery。
    
- Model Recovery。
    
- Robot Recovery。
    
- System Recovery。
    

尤其要有安全恢复状态检查，防止设备恢复连接时自动执行历史遗留的命令。

# 十、测试、基准与验证体系

你的 Benchmark 不能只测试 NPU 推理速度。

建议建立六套测试体系。

|测试|主要指标|
|---|---|
|OS Benchmark|启动时间、RSS、IPC 延迟、线程开销、组件恢复时间|
|Resource Benchmark|资源分配延迟、配额误差、资源泄漏|
|Inference Benchmark|首次延迟、稳态 P50/P95/P99、吞吐量、准确率|
|Heterogeneous Benchmark|数据搬运、NPU 等待、DMA、Cache 同步成本|
|Robotics Benchmark|控制周期、抖动、Deadline Miss、轨迹误差|
|Safety Benchmark|急停链路、故障检测延迟、错误命令拒绝、恢复正确性|

### 需要特别增加的验证

1. 故障注入

故意让：

- 推理服务崩溃。
    
- NPU 任务不返回。
    
- Buffer 不释放。
    
- 设备断开。
    
- IPC 中断。
    
- 机器人控制线程超时。
    

验证系统是否按照预定方式降级。

2. Sim-to-Real 对比

比较：

- 关节轨迹。
    
- 末端执行器位置。
    
- 速度误差。
    
- 控制延迟。
    
- 传感器反馈延迟。
    
- 仿真与真实环境的动力学差异。
    

3. 数值精度验证

比较 FP32、FP16、INT8、BF16、TF32 的结果，不能只看输出误差，还需要看端到端任务效果。

# 十一、从哪里开始：重新排列具体开发顺序

我建议不要把所有事情排成完全串行的九个里程碑。它们应当有四条并行的研发线。

开发总路线

1. P0：硬件与软件环境确认
    
    FMQL30TAI BSP、Linux Kernel、ICraft、DDR、DMA、NPU 驱动、工具链。
    
2. P1：Inference Proof of Concept
    
    tract CPU、ICraft NPU、C ABI、同模型精度和性能对照。
    
3. P2：Rust Hosted OS Core
    
    Resource Manager、Capability Manager、Component Manager、Supervisor。
    
4. P3：Robotics Proof of Concept
    
    ROS 2、ros2_control、MoveIt 2、仿真、故障注入。
    
5. P4：Home / Robot Integration
    
    Gateway、Command、Event、设备权限和跨领域资源管理。
    
6. P5：Resource Enforcement
    
    cgroups、seccomp、LSM、DMA、RT 和设备资源约束。
    
7. P6：Kernel Extension
    
    根据实际的安全缺口和性能测试进行最小 Linux 内核改造。
    
8. P7：Static Assurance
    
    Rust 类型系统、静态分析、MIR 分析、编译期约束。
    
9. P8：Native OS Research
    
    比较 Linux、seL4 和 Theseus 式架构，决定是否继续自研内核。
    

## 具体里程碑与验收

|里程碑|交付物|验收目标|
|---|---|---|
|M0|Hardware & BSP Report|完成板级硬件、内核和 ICraft 能力确认|
|M1|CPU Inference Backend|A53 上成功运行 ONNX|
|M2|ICraft Backend|ZG330 成功推理|
|M3|Rust Inference Manager|同一接口调用 CPU/NPU|
|M4|Linux Resource Manager|管理进程、内存、设备权限|
|M5|Component Manager|组件启动、停止、故障恢复|
|M6|Robotics Simulation|模拟机械臂完整运动链|
|M7|Robot Gateway|HA 业务可以提交机器人目标|
|M8|Hardware Integration|真实机器人运行、控制和故障测试|
|M9|Heterogeneous Resource Manager|CPU、NPU、PL、DMA 统一资源管理|
|M10|Linux Enforcement|将资源模型映射到内核强制机制|
|M11|Static Assurance|核心资源类型得到静态检查|
|M12|Native OS Evaluation|形成是否自研内核的技术决策|

有一个平台兼容问题需要提前注意。

目前 ICraft 官方公开页面列出了 Ubuntu 20.04 支持；ROS 2 Lyrical Luth 的 ARM64 Tier 1 平台是 Ubuntu 26.04，Ubuntu 24.04 是 Tier 3，而 Ubuntu 20.04 不在其支持表中。ROS 2 Humble 支持 Ubuntu 20.04 ARM64 的 Tier 3 源码构建，但它的支持周期到 2027 年 5 月。

复旦微 · 可编程逻辑器件+2

因此，不要现在就把 ROS 2 Lyrical 写死为目标板运行版本。

要先确认板卡 BSP、ICraft 版本、目标 Ubuntu、ROS 2 发行版是否能共存。开发机可以使用较新的 ROS 2，但目标板上的各个 ROS 2 节点最好保持兼容的运行环境。

# 十二、建议的项目目录

最终可以考虑把仓库组织成：

```
heterogeneous-os/
│
├── docs/
│   ├── architecture/
│   ├── security/
│   ├── resource-management/
│   ├── scheduling/
│   ├── hardware/
│   └── decisions/
│
├── os/
│   ├── crates/
│   │   ├── resource-manager/
│   │   ├── capability-manager/
│   │   ├── component-manager/
│   │   ├── lifecycle-manager/
│   │   ├── recovery-manager/
│   │   ├── ipc/
│   │   ├── scheduler/
│   │   └── telemetry/
│   │
│   ├── platform/
│   │   ├── linux/
│   │   └── native/
│   │
│   └── kernel/
│       ├── patches/
│       ├── drivers/
│       └── research/
│
├── inference/
│   ├── inference-api/
│   ├── inference-core/
│   ├── model-registry/
│   ├── tensor-manager/
│   ├── backend-cpu/
│   ├── backend-fpai/
│   ├── fpai-ffi/
│   ├── backend-pl/
│   └── benchmarks/
│
├── home/
│   ├── automation/
│   ├── devices/
│   ├── commands/
│   ├── events/
│   └── protocol-adapters/
│
├── robotics/
│   ├── description/
│   ├── controllers/
│   ├── planning/
│   ├── perception/
│   ├── hardware/
│   ├── simulation/
│   ├── gateway/
│   └── safety/
│
├── safety/
│   ├── policies/
│   ├── fault-models/
│   ├── watchdog/
│   └── hardware-interlocks/
│
├── tests/
│   ├── integration/
│   ├── fault-injection/
│   ├── performance/
│   ├── numerical-accuracy/
│   └── hardware-in-the-loop/
│
└── tools/
    ├── model-conversion/
    ├── board-bringup/
    ├── simulation/
    └── benchmarking/
```

这里是建议的目标目录，并不是说要立即创建所有目录。

# 十三、现在最先做的三件事

我建议你不要同时开十几个项目。先集中在三个技术验证上。

任务 A：FMQL30TAI 平台审计

最高优先级

确认当前 BSP、Kernel、ICraft Compiler/Runtime 版本、DMA 和内存布局，做一份硬件能力矩阵。

交付： `HARDWARE-CAPABILITY-MATRIX.md`

任务 B：Rust CPU/NPU 推理 PoC

用同一批模型比较 tract、ORT、ICraft，集中验证 C ABI、Buffer 生命周期和端到端推理性能。

交付： 可运行的 Rust Inference Demo 和基准数据。

任务 C：机器人仿真 PoC

在开发机上先构建 URDF、ros2_control、MoveIt 2 和 Gazebo 的完整执行链。

交付： 一个可运行、可注入故障的模拟机械臂。

这三项可以并行推进。OS 的第一阶段 Resource Manager 则围绕它们逐渐抽象，不需要凭空设计所有接口。

我的建议是，先不要开始写 Linux 内核补丁，更不要现在 Fork rustc。先把硬件、推理和机器人这三条真实工作负载跑起来。 它们会告诉我们系统究竟需要怎样的资源对象、隔离边界和执行合同。

最后，我认为你的原方案最值得保留的核心是：

> Rust 负责系统安全和资源管理；Linux 提供初期内核执行能力；ICraft 管理 NPU 内部执行；ROS 2 负责机器人领域运行时；独立控制器承担物理安全。

这五者之间的接口，才是整个项目最值得你自主设计的部分。

其中几个技术选择仍然需要通过实际硬件确认：尤其是 ICraft 的具体 FFI、NPU 多模型并发语义、DMA/IOMMU 能力，以及 FMQL30TAI 能否同时满足目标 ROS 2 发行版的运行环境。公开的 ICraft 资料能确认它提供编译、运行和任务管理能力，但具体 API、同步语义和设备驱动接口仍需以你拿到的 SDK 手册为准。
