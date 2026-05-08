# Python Async 简明报告

> 作者：AI Assistant  
> 日期：2025年

---

## 1. 什么是异步编程？

异步编程（Asynchronous Programming）是一种允许程序在等待某些操作（如 I/O、网络请求）完成时，继续执行其他任务的编程模式。与多线程不同，Python 的异步是**单线程、事件驱动**的并发模型。

---

## 2. 核心概念

### 2.1 `async` / `await`
- `async def` 定义一个**协程函数（coroutine function）**
- `await` 用于挂起当前协程，等待另一个协程或异步操作完成

```python
import asyncio

async def fetch_data():
    print("开始获取数据...")
    await asyncio.sleep(2)  # 模拟 I/O 等待
    print("数据获取完成")
    return {"data": 42}

asyncio.run(fetch_data())
```

### 2.2 事件循环（Event Loop）
事件循环是异步程序的核心调度器，负责管理和调度所有协程任务。

```python
loop = asyncio.get_event_loop()
loop.run_until_complete(fetch_data())
```

> Python 3.7+ 推荐直接使用 `asyncio.run()` 代替手动管理事件循环。

### 2.3 Task 与并发
使用 `asyncio.create_task()` 或 `asyncio.gather()` 实现真正的并发执行：

```python
async def main():
    # 并发执行多个协程
    results = await asyncio.gather(
        fetch_data(),
        fetch_data(),
        fetch_data(),
    )
    print(results)

asyncio.run(main())
```

---

## 3. 同步 vs 异步对比

| 特性         | 同步（Sync）       | 异步（Async）         |
|--------------|--------------------|-----------------------|
| 执行方式     | 顺序执行           | 并发执行（单线程）    |
| 等待 I/O 时  | 阻塞，CPU 空闲     | 切换执行其他任务      |
| 适用场景     | CPU 密集型任务     | I/O 密集型任务        |
| 编程复杂度   | 较低               | 较高                  |
| 代表库       | requests           | aiohttp、httpx        |

---

## 4. 常见使用场景

- **Web 服务**：FastAPI、Sanic 等异步 Web 框架
- **网络请求**：并发抓取多个 URL（aiohttp）
- **数据库访问**：异步 ORM（Tortoise-ORM、SQLAlchemy async）
- **消息队列**：异步消费 Kafka、RabbitMQ 等

---

## 5. 常见陷阱

1. **在异步上下文中调用阻塞函数**  
   如直接调用 `time.sleep()` 会阻塞整个事件循环，应使用 `asyncio.sleep()`。

2. **忘记 `await`**  
   协程函数不加 `await` 只会返回协程对象，不会执行。

3. **异步不等于多核并行**  
   `asyncio` 适合 I/O 密集型，CPU 密集型任务应使用 `multiprocessing`。

4. **混用同步与异步库**  
   同步库（如 `requests`）不能直接在异步代码中使用，需替换为异步等价库。

---

## 6. 快速参考

```python
# 定义协程
async def my_coroutine(): ...

# 运行入口
asyncio.run(my_coroutine())

# 并发任务
await asyncio.gather(coro1(), coro2())

# 创建后台任务
task = asyncio.create_task(my_coroutine())

# 超时控制
await asyncio.wait_for(my_coroutine(), timeout=5.0)
```

---

## 7. 总结

Python 的 `async/await` 语法简洁优雅，在处理高并发 I/O 场景时性能显著优于传统同步代码。掌握异步编程是构建现代高性能 Python 应用的必备技能。

---
*报告结束*
