# Backend

## 目录说明
该目录用于存放后端相关代码。

## 目录结构
```
backend/
├── api/           # API接口定义
├── core/          # 核心业务逻辑
├── services/      # 服务层实现
└── utils/         # 工具函数
```

## 技术栈
1. FastAPI 框架
2. MongoDB 数据库
3. Redis 缓存
4. gRPC 微服务通信

## 目录说明
- `api/`: REST API接口定义和路由
- `core/`: 核心业务逻辑和领域模型
- `services/`: 服务层实现和外部集成
- `utils/`: 工具函数和通用逻辑

## 开发规范
1. 遵循 RESTful API 设计规范
2. 使用依赖注入管理服务
3. 异步处理 I/O 操作
4. 完善的错误处理和日志记录
5. 单元测试覆盖率要求 > 80%

## 部署说明
1. 使用 Docker 容器化部署
2. 支持 Kubernetes 编排
3. 使用 Prometheus 监控
4. 使用 ELK 日志收集 