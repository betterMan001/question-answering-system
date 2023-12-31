'''
问答助手的主流程
run是启动的函数
'''
from ask_sys.base import prompt, msg
from ask_sys.plugin import ability_math, order_search, suggested_record
from ask_sys.knowledge_db import knowledge_db
import json
import openai
from configs import conf

sys_prompt = prompt.SysPrompt()  # prompt的框架
kdb = knowledge_db.KnowledgeDB()
msg = msg.Msg()  # msg列表，存放着要和gpt交互的上下文

openai.api_key = conf.get("api_key")


def run():
    # 初始化插件，这里的插件就是封装后的函数
    init_plugin()
    # msg是和模型对话的messages的工具类
    msg.set_sys_msg(sys_prompt.encode())

    # 模拟用户输入，实际场景中，往往会从Http请求中获取
    user_prompt = mock_user_prompt_search_order()
    # 查询知识库，这个就是建立的向量数据库
    result = kdb.search(user_prompt)

    knowledge = ""
    # 如果知识库查出内容，可将内容放入上下文
    if len(result["documents"]) > 0:
        knowledge = json.dumps(result["documents"])

    # 用户prompt加入上下文
    msg.add_user_msg(sys_prompt.build_prompt(
        user_prompt=user_prompt, knowledge=knowledge))

    # 将message发给gpt，获得GPT返回的结果
    gpt_msg = request_gpt()

    # 系统回复加入上下文
    msg.add_gpt_reponse(gpt_msg.content)

    # 处理GPT响应，并兼容gpt返回的不稳定性
    response = json.loads(gpt_msg.content)
    if response.get("response") is not None:
        response = response.get("response")

    if not isinstance(response, dict):
        print(response)  # 查看错误的gpt情况
    elif response.get("normal") is not None:
        print(response["normal"])
    else:
        # 调用插件并且把结果继续给gpt对话下去
        call_plugin(response, user_prompt=user_prompt)


# 根据gpt响应 进行插件调用
def call_plugin(response, user_prompt):
    plugins = sys_prompt.get_plugins()
    for pluginName, plugin in plugins.items():
        if response.get(pluginName) is not None:
            run_result = plugin.run(response.get(pluginName))

            # 为了兼容GPT-3.5的理解能力，需要暂时将SysPrompt变为无插件的版本
            # 获取到插件的结果之后，去掉询问插件的几个msg，直接把插件的结果作为上下文，这样可以避免多轮的function call对3.5理解上的受损
            msg.set_sys_msg(sys_prompt.encode_no_plugin())
            # 去除有插件版本的聊天
            msg.remove_last(2)
            msg.add_user_msg(sys_prompt.build_prompt(
                user_prompt=user_prompt, knowledge=json.dumps(run_result)))

            print(request_gpt().content)

            # 恢复插件版的SysPrompt
            msg.set_sys_msg(sys_prompt.encode())

            break


# 与GPT交互
def request_gpt():
    chat_completion = openai.ChatCompletion.create(
        # 选择的GPT模型
        model="gpt-3.5-turbo-16k-0613",
        # 上下文
        messages=msg.encode(),
        # 0.2降低GPT回答的随机性
        temperature=0.2,
        # 0.2降低GPT回答的随机性
        top_p=0.2,
        # 不采用流式输出
        stream=False,
    )

    return chat_completion.choices[0].message


def mock_user_prompt_search_order():
    return "帮我查下订单信息，订单号：123456"


def mock_user_prompt_ask_company_culture():
    return "咱公司有啥企业文化？"


# 初始化插件
def init_plugin():
    sys_prompt.add_plugin(ability_math.Math())
    sys_prompt.add_plugin(order_search.OrderSearch())
    sys_prompt.add_plugin(suggested_record.SuggestedRecord())


if __name__ == "__main__":
    while 1:  # 多轮对话
        run()
