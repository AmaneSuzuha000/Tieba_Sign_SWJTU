from DrissionPage import ChromiumOptions, ChromiumPage
import json
import os
import shutil
import time
import requests

def read_cookie():
    if "TIEBA_COOKIES" in os.environ:
        return json.loads(os.environ["TIEBA_COOKIES"])
    else:
        print("贴吧Cookie未配置！")
        return []

def reply_specified_post(page, post_url, reply_content):
    print(f"\n开始对目标帖子执行4次回复，内容：{reply_content}")
    for reply_idx in range(1, 5):
        try:
            # 每次回复前重新打开帖子
            page.get(post_url)
            page._wait_loaded(10)

            ueditor_box = page.ele('xpath://*[@id="ueditor_replace"]', timeout=10)
            if ueditor_box:
                ueditor_box.click()
            ueditor_p = page.ele('xpath://*[@id="ueditor_replace"]/p', timeout=10)
            if ueditor_p:
                ueditor_p.click()
                ueditor_p.clear()
                ueditor_p.input(reply_content)

            submit_btn = page.ele('xpath://*[@id="tb_rich_poster"]/div[3]/div[3]/div/a', timeout=5)
            if not submit_btn:
                submit_btn = page.ele('xpath://*[@id="tb_rich_poster"]/div[3]/div[3]/div/a/span', timeout=5)
            if submit_btn:
                try:
                    submit_btn.click()
                    time.sleep(2)
                    print(f"第{reply_idx}次回复成功！")
                except Exception as e:
                    print(f"第{reply_idx}次回复异常：{str(e)}")
            else:
                print(f"第{reply_idx}次回复失败：未找到任何提交按钮")

        except Exception as e:
            print(f"第{reply_idx}次回复异常：{str(e)}")
        time.sleep(5)
    print("4次回复任务执行完毕！\n")
    
if __name__ == "__main__":
    print("程序开始运行")
    notice = ''
    co = ChromiumOptions().headless()
    chromium_path = shutil.which("chromium-browser")
    if chromium_path:
        co.set_browser_path(chromium_path)

    page = ChromiumPage(co)

    url = "https://tieba.baidu.com/"
    page.get(url)
    page.set.cookies(read_cookie())
    page.refresh()
    page._wait_loaded(15)

    onekey_box = page.ele('xpath://*[@id="onekey_sign"]/a', timeout=10)
    if onekey_box:
        onekey_box.click()
        print("找到一键签到按钮")
    sign_box = page.ele('xpath://*[@id="dialogJbody"]/div/div/div[1]/a', timeout=10)
    if sign_box:
        sign_box.click()
        print("签到成功")
    
    TARGET_POST_URL = "https://tieba.baidu.com/p/9983496041"  # 目标帖子链接
    REPLY_CONTENT = "3"  # 回复文本
    reply_specified_post(page, TARGET_POST_URL, REPLY_CONTENT)
    
    if "SendKey" in os.environ:
        api = f'https://sc.ftqq.com/{os.environ["SendKey"]}.send'
        title = u"贴吧签到信息"
        data = {
        "text":title,
        "desp":notice
        }
        try:
            req = requests.post(api, data=data, timeout=60)
            if req.status_code == 200:
                print("Server酱通知发送成功")
            else:
                print(f"通知失败，状态码：{req.status_code}")
                print(api)
        except Exception as e:
            print(f"通知发送异常：{e}")
    else:
        print("未配置Server酱服务...")
