from DrissionPage import ChromiumOptions, ChromiumPage
import json
import os
import shutil
import time
import requests

def read_cookie():
    """读取 cookie，优先从环境变量读取"""
    if "TIEBA_COOKIES" in os.environ:
        return json.loads(os.environ["TIEBA_COOKIES"])
    else:
        print("贴吧Cookie未配置！详细请参考教程！")
        return []

def get_level_exp(page):
    """获取等级和经验，如果找不到返回'未知'"""
    try:
        level_ele = page.ele('xpath://*[@id="pagelet_aside/pagelet/my_tieba"]/div/div[1]/div[3]/div[1]/a/div[2]').text
        level = level_ele if level_ele else "未知"
    except:
        level = "未知"
    try:
        exp_ele = page.ele('xpath://*[@id="pagelet_aside/pagelet/my_tieba"]/div/div[1]/div[3]/div[2]/a/div[2]/span[1]').text
        exp = exp_ele if exp_ele else "未知"
    except:
        exp = "未知"
    return level, exp

# 新增：指定帖子循环回复4次的函数
def reply_specified_post(page, post_url, reply_content):
     """
     指定帖子循环回复4次（修复连接断开问题）
     :param page: 浏览器页面对象
     :param post_url: 目标帖子完整链接
     :param reply_content: 要回复的内容
     """
     print(f"\n开始对目标帖子执行4次回复，内容：{reply_content}")
     for reply_idx in range(1, 5):
         retry = 3  # 单次回复重试3次
         success = False
         while retry > 0 and not success:
             try:
                 # 重新打开页面，强制等待加载完成
                 page.get(post_url)
                 page.wait.load_start(timeout=10)  # 等待页面开始加载
                 page.wait.load_complete(timeout=20) # 等待页面完全加载
                 time.sleep(2) # 额外延迟，避免连接不稳
                 # 定位回复框（兼容贴吧新版/旧版）
                 reply_input = page.ele('xpath://textarea[@class="j_paste copyable"]', timeout=15)
                 if not reply_input:
                     reply_input = page.ele('xpath://textarea[contains(@class,"post_content")]', timeout=10)
                 if not reply_input:
                     print(f"第{reply_idx}次回复：未找到回复输入框")
                     break
                 # 清空输入框+输入内容（避免残留）
                 reply_input.clear()
                 reply_input.input(reply_content)
                 time.sleep(1)
                 # 定位提交按钮（多选择器兼容）
                 submit_btn = page.ele('xpath://button[@class="btn btn_submit j_submit"]', timeout=10)
                 if not submit_btn:
                     submit_btn = page.ele('xpath://a[@class="btn_submit"]', timeout=5)
                 if submit_btn:
                     submit_btn.click()
                     time.sleep(3) # 提交后延迟，确保成功+稳定连接
                     print(f"第{reply_idx}次回复成功！")
                     success = True
                 else:
                     print(f"第{reply_idx}次回复：未找到提交按钮")
                     retry -=1
                     time.sleep(2)
             except Exception as e:
                 retry -=1
                 print(f"第{reply_idx}次回复重试({3-retry}/3)，异常：{str(e)}")
                 time.sleep(3) # 重试前延迟，恢复连接
         if not success:
             print(f"第{reply_idx}次回复失败（已重试3次）")
         time.sleep(4) # 每次回复间隔拉长，避免风控+断连
     print("4次回复任务执行完毕！\n")
    
if __name__ == "__main__":
    print("程序开始运行")

    # 通知信息
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


    over = False
    yeshu = 0
    count = 0

    while not over:
        yeshu += 1
        page.get(f"https://tieba.baidu.com/i/i/forum?&pn={yeshu}")

        page._wait_loaded(15)

        for i in range(2, 22):
            element = page.ele(
                f'xpath://*[@id="like_pagelet"]/div[1]/div[1]/table/tbody/tr[{i}]/td[1]/a/@href'
            )
            try:
                tieba_url = element.attr("href")
                name = element.attr("title")
            except:
                msg = f"全部爬取完成！本次总共签到 {count} 个吧..."
                print(msg)
                notice += msg + '\n\n'
                page.close()
                over = True
                break

            page.get(tieba_url)
            

            page.wait.eles_loaded('xpath://*[@id="signstar_wrapper"]/a/span[1]',timeout=30)


            # 判断是否签到
            is_sign_ele = page.ele('xpath://*[@id="signstar_wrapper"]/a/span[1]')
            is_sign = is_sign_ele.text if is_sign_ele else ""
            if is_sign.startswith("连续"):
                level, exp = get_level_exp(page)
                msg = f"{name}吧：已签到过！等级：{level}，经验：{exp}"
                print(msg)
                notice += msg + '\n\n'
                print("-------------------------------------------------")
            else:
                page.wait.eles_loaded('xpath://a[@class="j_signbtn sign_btn_bright j_cansign"]',timeout=30)
                sign_ele = page.ele('xpath://a[@class="j_signbtn sign_btn_bright j_cansign"]')
                if sign_ele:
                    sign_ele.click()
                    time.sleep(1)  # 等待签到动作完成
                    sign_ele.click()
                    time.sleep(1)  # 等待签到动作完成
                    page.refresh()

                    page._wait_loaded(15)

                    level, exp = get_level_exp(page)
                    msg = f"{name}吧：成功！等级：{level}，经验：{exp}"
                    print(msg)
                    notice += msg + '\n\n'
                    print("-------------------------------------------------")
                else:
                    msg = f"错误！{name}吧：找不到签到按钮，可能页面结构变了"
                    print(msg)
                    notice += msg + '\n\n'
                    print("-------------------------------------------------")

            count += 1
            page.back()
            page._wait_loaded(10)
    
    # ===================== 新增：签到完成后执行4次回复 =====================
    # 需修改这里的 帖子链接 和 回复内容（必填！）
    TARGET_POST_URL = "https://tieba.baidu.com/p/9983496041"  # 替换成你的目标帖子完整链接
    REPLY_CONTENT = "3"                            # 替换成你要回复的文本
    if TARGET_POST_URL != "https://tieba.baidu.com/p/xxxxxxxxxxx" and REPLY_CONTENT:
        reply_specified_post(page, TARGET_POST_URL, REPLY_CONTENT)
    else:
        print("未配置目标帖子链接或回复内容，跳过回复任务")
    # ======================================================================

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
