# 纯米智能电压力锅 Home Assistant 自定义集成 (Chunmi Electric Pressure Cooker)

[![HACS Default](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/github/v/release/931122/chunmi_pre_cooker_eh1)](https://github.com/931122/chunmi_pre_cooker_eh1/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

专为 **米家智能电压力锅 5L (`chunmi.pre_cooker.eh1`)** 打造的 Home Assistant 深度定制集成。

---

## 解决的痛点

在官方 `xiaomi_home` 集成中，由于米家官方 MIoT-Spec 物模型并未开放该型号的启动/停止动作，导致在 Home Assistant 中**只能查看部分状态，无法选择烹饪模式、口感和保压时间，也无法开始烹饪**。

此外，该设备搭载的 ESP32 固件限制了局域网未经认证的裸写操作（直接通过 UDP 发送 `set_start` 会被拦截并报错 `[4]`）。

本集成通过逆向解析米家官方通信协议与烹饪曲线码（`cookCode`），实现了：
1. **完整的本地只读传感器监听**（局域网 UDP 毫秒级直接轮询）。
2. **多模式智能启动控制**（协同中枢网关 MIPS RPC 通道或局域网协议下发烹饪程序）。
3. **原生 UI 实体支持**：内置模式下拉选择框、**口感偏好选择**、**保压时间滑动条**、控制按钮、倒计时与压力/温度监控。

---

## 支持功能与实体列表

### 1. 烹饪模式与口感选择 (`select`)
无需编写任何 YAML 脚本，开箱即用：
* **烹饪模式选择** (`select.chun_mi_dian_ya_li_guo_ya_li_guo_peng_ren_mo_shi_xuan_ze`)
  * 支持：**大米饭**、**杂粮饭**、**煮粥**、**煲汤**、**牛羊肉**、**排骨**、**鸡鸭肉**、**筋蹄**、**低温慢煮**、**开盖煮**、**蒸煮**、**保温** 等。
* **口感偏好** (`select.chun_mi_dian_ya_li_guo_ya_li_guo_kou_gan_pian_hao`)
  * **随模式自动动态联动**：
    * 米饭/杂粮类：自动呈现 **软糯 (30kPa)** / **适中 (45kPa)** / **弹润 (60kPa)**
    * 肉类/排骨类：自动呈现 **酥软 (40kPa)** / **适中 (50kPa)** / **嚼劲 (60kPa)**
    * 汤类/收汁类：自动呈现 **香浓** / **适中** / **清鲜**

### 2. 保压时间调节 (`number`)
* **保压时间** (`number.chun_mi_dian_ya_li_guo_ya_li_guo_bao_ya_shi_jian`)
  * 滑动调节保压时长（单位：分钟）。
  * 滑块的调节上下限会**根据当前选中的菜谱自动匹配硬件安全范围**（例如大米饭 6~25 分钟，牛羊肉 15~60 分钟），切换模式时自动重置为推荐值。

### 3. 快捷动作按钮 (`button`)
* **开始烹饪**：根据当前选中的模式、口感与保压时间，自动动态合成加热曲线与 CRC16 校验码并一键启动。
* **停止烹饪**：随时终止当前烹饪程序并退出高压模式。
* **开盖收汁**：一键开启大火无压收汁。
* **开始保温**：一键进入恒温保温状态。

### 4. 实时传感器 (`sensor`)
* **工作状态**：待机 / 烹饪中 / 保温中 / 预约中 / 暂停中
* **剩余时间**：精准展示当前烹饪/保温剩余倒计时（分钟）
* **当前压力**：锅内实时压力（kPa）
* **锅内温度**：实时温度（°C）
* **当前烹饪模式**：实时解码设备正在运行的菜谱名称
* **锅盖合盖状态**：已合盖到位 / 未合好/开盖（微动开关 1）
* **手柄锁止状态**：已旋转锁死 / 未锁紧（微动开关 2）

### 5. 服务调用 (`Services`)
可在自动化（Automations）或脚本中直接调用：
* `chunmi_pre_cooker.start_cooking`：
  * `mode` (可选): 模式名称（如 "大米饭"、"土豆炖排骨"）
  * `taste` (可选): 口感（如 "软糯"、"适中"、"嚼劲"，或索引 0/1/2）
  * `duration` (可选): 保压时间（分钟，如 20）
  * `cook_code` (可选): 纯米专属 358 位 Hex 自定义加热曲线
* `chunmi_pre_cooker.cancel_cooking`：停止当前烹饪。

---

## 安装方法

### 方式一：通过 HACS 自定义仓库添加（推荐）
1. 打开 Home Assistant 的 **HACS** 页面。
2. 点击右上角的三个点 -> **自定义代码库 (Custom repositories)**。
3. 输入 Repository: `https://github.com/931122/chunmi_pre_cooker_eh1`，类别选择 **集成 (Integration)**。
4. 点击添加后，在 HACS 列表搜索 **Chunmi Electric Pressure Cooker** 并下载安装。
5. 重启 Home Assistant。

### 方式二：手动安装
1. 下载本项目 Release 或源码中的 `custom_components/chunmi_pre_cooker` 文件夹。
2. 将其复制到 Home Assistant 配置目录下的 `custom_components` 文件夹中（如 `/config/custom_components/chunmi_pre_cooker`）。
3. 重启 Home Assistant。

---

## 添加与配置

1. 在 Home Assistant 中进入 **设置 (Settings)** -> **设备与服务 (Devices & Services)**。
2. 点击右下角 **添加集成 (Add Integration)**。
3. 搜索 **纯米** 或 **chunmi**，选择 **纯米智能电压力锅**。
4. **全自动凭证探测**：
   * 集成向导会自动读取宿主机上现有米家存储凭证，并自动在局域网内探测识别电压力锅的内网 IP、DID 与 Token。
   * 确认信息无误后点击 **提交 (Submit)** 即可立即生成所有设备与实体！

---

## 注意事项

* **烹饪安全锁机制**：电压力锅具备硬件级机械防爆安全联锁。启动任何需要加压的烹饪模式前，请先**合好锅盖**并将手柄旋钮**顺时针旋紧锁死**；若处于开盖或未旋死状态下发启动，系统会弹出通知提醒且设备将拒绝升压加热。
* **控制权限与中枢网关**：设备固件内置写拦截保护。如果需要从 Home Assistant 中直接下发“开始烹饪”控制命令，建议保持 `xiaomi_home` 集成及局域网内小米中枢网关在线。

---

## License

[MIT License](LICENSE)
