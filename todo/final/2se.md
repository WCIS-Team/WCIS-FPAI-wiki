A. 板卡与 Linux
[ ] 板卡完整型号、PCB 版本和 SoC 料号
[ ] BSP、Bootloader、Linux 发行版和 Kernel 版本
[ ] AArch64 / 32-bit ABI、CPU 核心和实际频率
[ ] Kernel Config、PREEMPT_RT 和定时器支持
[ ] cgroups v2、Namespace、seccomp、LSM 支持情况
[ ] PS DDR、Reserved Memory、CMA 和实际可用内存

B. ZG330 / ICraft
[ ] Compiler、Runtime、SDK 的精确版本
[ ] C++ API、头文件、链接库和目标 ABI
[ ] ONNX Opset、算子、Shape、Layout 支持矩阵
[ ] FP16、INT8、BF16、TF32 的逐算子支持矩阵
[ ] Session、Job、Tensor、并发和取消能力
[ ] ICraft Scheduler 在 ZG330 上是否存在及其 API
[ ] Buffer 分配、导入、同步、错误和复位接口

C. DDR / DMA / FPGA
[ ] PS、NPU、PL 可访问的物理内存范围
[ ] DMA Controller、DMA 地址和地址转换方式
[ ] IOMMU/SMMU 是否存在并实际启用
[ ] Cache Coherency、Flush、Invalidate 规则
[ ] DMA Buffer 对齐、大小、映射和生命周期限制
[ ] PL AXI 接口、IRQ、时钟、Reset 和重配置能力
[ ] 实际 PS ↔ PL ↔ NPU 数据流和带宽

D. CPU 推理与 AI
[ ] tract 对目标模型算子和 Shape 的覆盖
[ ] ORT 在目标系统上的 ABI 和依赖情况
[ ] 模型在 A53 上的加载、RSS、延迟和吞吐
[ ] ICraft 的模型格式和版本兼容矩阵
[ ] 整模型 CPU/NPU 选择的收益
[ ] 子图混合执行是否有可用接口和实际收益

E. 机器人硬件与安全
[ ] 机械臂型号、自由度、负载和关节参数
[ ] 驱动器型号、总线协议和厂商 SDK
[ ] 电流环、速度环、位置环分别在哪里执行
[ ] 控制频率、通信延迟、抖动和反馈频率
[ ] 编码器、力矩传感器和其他反馈接口
[ ] 急停、制动、STO、限位和 Watchdog
[ ] 主机断电、程序崩溃和通信丢失时的硬件行为

F. ROS 2 与仿真
[ ] ROS 2 发行版与板端 Ubuntu/BSP 兼容性
[ ] Fast DDS、Cyclone DDS、Zenoh 的可用版本
[ ] ros2_control、MoveIt 2 和 Gazebo 版本兼容性
[ ] 真实机器人是否有 ROS 2 Hardware Interface
[ ] 仿真模型的惯量、摩擦、执行器和传感器参数
[ ] HIL/SIL、系统辨识、标定和故障注入条件

G. 架构决策
[ ] 最终采用 Linux、混合内核、seL4 还是 Theseus 式架构
[ ] 组件使用线程、进程还是独立执行域
[ ] 统一调度模型与各领域调度器如何分工
[ ] CPU/NPU/PL/设备资源如何统一申请和释放
[ ] IPC、数据面和控制面的通信方案
[ ] Capability 的授权、委托和撤销机制
[ ] 哪些安全约束需要内核强制执行
[ ] 哪些约束可以用 Rust 类型与静态分析验证
[ ] 哪些情况下才有必要修改 rustc