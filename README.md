# AkuzoiAI MCDR

AI assistant for MCDR

```
!!ai clear        — 清空全局对话历史（权限：ADMIN）
!!ai reload       — 热重载配置文件（权限：ADMIN）
!!ai status       — 查看当前预设/模型/历史条数/在线玩家数（权限：min_permission_to_use）
!!ai preset list  — 列出所有预设（权限：ADMIN）
!!ai preset switch <name>  — 切换激活预设（权限：ADMIN）
!!ai <message>    — 主入口（权限：min_permission_to_use）
```

# MCP
```
"mcpServers": {
  "playwright": {
    "command": "npx",
    "args": ["@playwright/mcp@latest"]
  },
  "context7": {
    "url": "https://mcp.context7.com/mcp",
    "headers": {
      "Authorization": "Bearer YOUR_API_KEY"
    }
  }
}
```

# Acknowledgements
- [Yunmoan/AkuzoiAI-bukkit](https://github.com/Yunmoan/AkuzoiAI-bukkit)