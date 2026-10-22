# Hosted environment feasibility, 2026-10-22

Status: **evidence collection only; zero approved environments**.

[Implementation](IMPLEMENTATION.md) · [中文实现说明](IMPLEMENTATION.zh-CN.md)

The investigation read published inventories and upstream source documentation. It did not start a runner, download an executable, install dependencies or establish source-to-binary equivalence. Absence from an inventory means there is no documented basis to select that interpreter; it is not a claim to have inspected every file on an actual machine.

## Published inventory snapshot

All inventory links below are pinned to `actions/runner-images` commit `c87f6f636fffa43205bc05328efe9958af0f984f`. Values are reported by those documents and do not imply present job availability or approval.

| Image | Published image version | Architecture | Listed CPython 3.10 | Listed CPython 3.13 |
| --- | --- | --- | --- | --- |
| [Ubuntu 24.04](https://github.com/actions/runner-images/blob/c87f6f636fffa43205bc05328efe9958af0f984f/images/ubuntu/Ubuntu2404-Readme.md) | 20261012.334.1 | x64 | 3.10.22 | 3.13.16 |
| [Windows 2025 VS2026](https://github.com/actions/runner-images/blob/c87f6f636fffa43205bc05328efe9958af0f984f/images/windows/Windows2025-VS2026-Readme.md) | 20261007.264.1 | x64 | 3.10.11 | 3.13.16 |
| [macOS 26 ARM](https://github.com/actions/runner-images/blob/c87f6f636fffa43205bc05328efe9958af0f984f/images/macos/macos-26-arm64-Readme.md) | 20261013.0424.1 | arm64 | Not listed | 3.13.16 |
| [macOS 15 ARM](https://github.com/actions/runner-images/blob/c87f6f636fffa43205bc05328efe9958af0f984f/images/macos/macos-15-arm64-Readme.md) | 20260907.0337.1 | arm64 | Not listed | 3.13.15 |
| [macOS 14 ARM](https://github.com/actions/runner-images/blob/c87f6f636fffa43205bc05328efe9958af0f984f/images/macos/macos-14-arm64-Readme.md) | 20260831.0302.1 | arm64 | Not listed | 3.13.15 |
| [Xcode 27 ARM preview](https://github.com/actions/runner-images/blob/c87f6f636fffa43205bc05328efe9958af0f984f/images/macos/xcode-27-arm64-Readme.md) | 20261012.0260.1 | arm64 | Not listed | 3.13.16 |
| [macOS 26 Intel](https://github.com/actions/runner-images/blob/c87f6f636fffa43205bc05328efe9958af0f984f/images/macos/macos-26-Readme.md) | 20260824.0517.1 | x64 | Not listed | 3.13.15 |
| [macOS 15 Intel](https://github.com/actions/runner-images/blob/c87f6f636fffa43205bc05328efe9958af0f984f/images/macos/macos-15-Readme.md) | 20260824.0482.1 | x64 | 3.10.21 | 3.13.15 |

The [image catalog at the same revision](https://github.com/actions/runner-images/blob/c87f6f636fffa43205bc05328efe9958af0f984f/README.md) marks macOS 14 deprecated and Xcode 27 preview. It explains that images change regularly and historical image builds are not guaranteed reproducible. Pinning these documentation links captures evidence; it does not pin a hosted VM.

No reviewed standard ARM macOS option for Python 3.10 was established. The Intel option would change the tested architecture, so it is not substituted. PyPy 3.10 entries in some inventories are not CPython replacements for the existing matrix.

## Provenance and lifecycle gaps

At `actions/python-versions` commit `9834b4e4911ca2950ff6c3b7547f09eacc006848`, the [upstream build description](https://github.com/actions/python-versions/blob/9834b4e4911ca2950ff6c3b7547f09eacc006848/README.md) describes source builds for Ubuntu and older macOS Python versions, and redistribution of official binaries for Windows and newer macOS Python versions. These descriptions are useful starting points, not verification of the precise artifacts installed in these images. Build dependencies, installer side effects, native libraries and artifact/source correspondence remain unreviewed. The general description also cannot override the observed macOS 3.10 installation log in the original proposal.

Python's [version lifecycle](https://devguide.python.org/versions/) lists 3.10 as end-of-life on **2026-10-01**. The [3.10.22 release](https://www.python.org/downloads/release/python-31022/) confirms that it is the final security release and is source-only; 3.10.11 was the last release with binary installers. Consequently, the Windows 3.10.11 and Intel macOS 3.10.21 inventory entries are not the final 3.10 patch, and even 3.10.22 no longer receives future upstream security fixes. This is a separate issue from provenance. No individual vulnerability exposure of this starter is asserted without analysis.

## Concrete next choices

| Route | Necessary work | Current decision |
| --- | --- | --- |
| Preserve all six cells and the Python 3.10 compatibility promise | Establish reviewed prebuilt environments outside candidate jobs, including ARM macOS; separately decide whether and how to retain isolated legacy testing after 3.10 end-of-life | No infrastructure or legacy-policy exception approved |
| Migrate the minimum supported Python version | Separate compatibility proposal with README, prompts, installer expectations and CI updated together; retain three-platform coverage and test the actual replacement matrix | Not silently applied to PR #4 or this implementation |
| Switch macOS to Intel or omit a failing cell | Alters existing coverage without resolving provenance or lifecycle | Not selected |

Neither viable route is ready for activation. A custom environment additionally needs an owner, provider, capacity/budget decision, single-job isolation, trusted bootstrap, reviewed image construction and update process, and evidence for all required components. Cost cannot be stated reliably before a provider and operating model are selected. No paid resources have been created.

The immediate deliverable is the offline validator and its regression tests. The live workflow and PR #4 remain unchanged. The remaining decisions are about the supported Python baseline and a demonstrably trusted execution environment, not whether to accept an unexplained green badge.

## 中文结论

本次固定读取八份官方镜像清单。macOS 26／15／14 和 Xcode 27 ARM 清单均未列出 CPython 3.10；macOS 15 Intel 有 3.10.21，但不能默默改变原有 ARM 覆盖。Windows 列出的 3.10.11 也不是 3.10 最终补丁版。

Python 官方确认 3.10 已于 2026-10-01 结束支持，最终版为仅提供源码的 3.10.22。因此需要分别解决来源审查与旧版支持策略：保留六组覆盖就需要已审查的隔离旧版环境；迁移最低 Python 版本则应另立兼容性变更，同步文档、安装预期和三平台测试。当前均未擅自执行，也未购买基础设施。公开源码、预装清单和已有绿灯都不能直接证明安装产物满足来源要求。
