# PaperAgent 对 PaperClaw Academic v1 的消费约束

PaperAgent 不拥有论文事实模型，也不得读取 PaperClaw SQLite、页面缓存或索引文件。
`contracts/academic.v1.schema.json` 和 golden payload 是 PaperClaw canonical contract
的 byte-equivalent 消费副本。

- Python 3.12 安装 `PaperAgent[paperclaw]` 后直接使用 PaperClaw canonical classes。
- Python 3.11 只使用内部 `EvidenceLocatorView` 做 structural validation；该 view
  不是第二套 wire contract。
- PaperClaw `EvidenceBundle` 由 adapter 转换为 PaperAgent
  `AcademicEvidenceLedger`，Accepted/Rejected/Conflicted 仍由 PaperAgent 决定。
- 未知 schema major、locator/source hash 不一致或 resolve 返回不同对象时 fail closed。
- `AcademicLocator` 是旧调用的临时 alias，新代码使用 `EvidenceLocatorView` 或
  PaperClaw `EvidenceLocator`。
