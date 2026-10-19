# Go harness example

A small, runnable example of registering a Go module as an explicit project in the starter's harness. It is documentation only: the starter itself does not need Go, nothing here is run by the default Python checks or CI, and no toolchain is installed for you.

Tested with Go 1.22.2 on Linux. The `go.mod` declares `go 1.22`; newer Go versions should also work, but verify on your own machine.

## What is in it

| Path | Purpose |
| --- | --- |
| `go.mod` | Standalone module with no third-party dependencies |
| `lessons/lessons.go` | `IsDue`: a lesson is due for review on its review date or later |
| `lessons/lessons_test.go` | Table-driven passing test (before, on and after the review date) |
| `lessons/failing_test.go` | Deliberately failing test, compiled only with `-tags failing` |

## Run it with Go directly

```sh
cd examples/go-harness
go test ./...                 # passes, exit 0
go test -tags failing ./...   # fails on purpose, exit 1
```

## Run it through the harness

In a project created by `tools/bootstrap.py`, copy this directory to the same relative path, then replace `harness/config.json`. Do not register this example in a real project unless you actually use Go there.

```json
{
  "schema_version": 1,
  "projects": [{
    "name": "go-example",
    "path": "examples/go-harness",
    "required": ["test"],
    "checks": {
      "test": {"commands": [["go", "test", "./..."]], "timeout_seconds": 120}
    }
  }]
}
```

```sh
python3 harness/run.py check
```

Expected result: `ok` for the `lessons` package, then `PASS: selected configured checks`, exit code 0.

For the failing variant, change the command to `["go", "test", "-tags", "failing", "./..."]`. Expected result: `--- FAIL: TestIntentionallyFailing`, then `FAIL go-example/test` on stderr, and the harness exits **1**. The harness reports failure, not Go's exact exit code, and it does not continue to later checks.

If `go` is not on `PATH`, the harness prints `NOT_AVAILABLE: executable not found` and exits **2**. That is not a pass.

The failing command exists only to show failure propagation. Never register it as a required check.

## 中文说明

这是一个可运行的小例子，演示如何把 Go 模块注册为 harness 的显式项目。它只是文档示例：模板本身不需要 Go，默认的 Python 检查和 CI 不会运行它，也不会替你安装工具链。

已在 Linux 上用 Go 1.22.2 验证。使用步骤：

1. 进入目录运行 `go test ./...`，应当通过，退出码为 0。
2. 运行 `go test -tags failing ./...`，会故意失败，退出码为 1。
3. 在用 `tools/bootstrap.py` 生成的项目里，把本目录复制到同样的相对路径，并按上面的 JSON 配置 `harness/config.json`，然后运行 `python3 harness/run.py check`。通过时输出 `PASS: selected configured checks`；失败变体时 harness 退出码为 1；找不到 `go` 时输出 `NOT_AVAILABLE` 并以退出码 2 结束。

故意失败的命令只用于演示失败传播，请不要把它登记为真实项目的必需检查。
