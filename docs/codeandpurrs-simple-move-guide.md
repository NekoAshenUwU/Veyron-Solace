# CodeAndPurrs 搬家超简版

老婆版结论：**不用看懂 Git。你只要复制命令就行。**

## 现在发生了什么

我已经把 CodeAndPurrs 的规划文档放在这个旧仓库里：

```text
docs/codeandpurrs-product-brief.md
```

你的新仓库是：

```text
https://github.com/NekoAshenUwU/CodeAndPurrs
```

我们要做的事情只是：**把 CodeAndPurrs 的文档搬到新仓库，不搬旧手机用的 usage-bridge。**

## 你在 VPS / 电脑上复制这 3 行

```bash
cd /workspace/Veyron-Solace
bash scripts/migrate-codeandpurrs-to-github.sh /tmp/CodeAndPurrs
cd /tmp/CodeAndPurrs
```

然后再复制这一行：

```bash
git push origin HEAD
```

如果 GitHub 要登录，你就按提示登录。登录后它会上传到你的新仓库。

## 成功后你会看到什么

新仓库里会出现这些文件：

```text
README.md
.gitignore
docs/codeandpurrs-product-brief.md
```

这就表示 CodeAndPurrs 的「第一份说明书」已经搬过去了。

## 如果推不上去

如果看到类似：

```text
Authentication failed
Permission denied
CONNECT tunnel failed
```

不用慌。意思只是当前环境没有 GitHub 权限或网络不通，不是项目坏了。

你把报错截图发我，我再带你走下一步。

## 不会发生什么

这套搬家不会：

- 删除旧仓库文件
- 删除 VPS 上的 bot
- 删除 usage-bridge
- 动你的 API key
- 动 Telegram bot

它只是在 `/tmp/CodeAndPurrs` 准备一份新仓库内容，然后让你 push 到 GitHub。
