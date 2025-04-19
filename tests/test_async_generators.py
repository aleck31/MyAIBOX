import asyncio
import gradio as gr
import time


async def async_iteration(count: int):
    for i in range(count):
        yield i*'x'
        await asyncio.sleep(1)


def iteration(count: int):
    for i in range(count):
        yield i*'x'
        time.sleep(1)


# with gr.Blocks() as demo:
#     with gr.Row():
#         with gr.Column():
#             num1 = gr.Number(value=4, precision=0)
#             o1 = gr.Number()
#             async_iterate = gr.Button(value="Async Iteration")
#             async_iterate.click(async_iteration, num1, o1)
#         with gr.Column():
#             num2 = gr.Number(value=4, precision=0)
#             o2 = gr.Number()
#             iterate = gr.Button(value="Iterate")
#             iterate.click(iteration, num2, o2)

app1 = gr.Interface(async_iteration, gr.Number(precision=0, value=10), gr.Textbox())
app2 = gr.Interface(iteration, gr.Number(precision=0, value=10), gr.Textbox())

with gr.Blocks() as demo:
    with gr.Row():
        app1.render()
    with gr.Row():
        app2.render()

demo.queue(
    # default_concurrency_limit=20
    ).launch()