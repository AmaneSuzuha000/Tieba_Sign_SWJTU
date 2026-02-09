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

def get_level_exp(page):
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


    over = False
    yeshu = 0
    count = 0
    is_first_tieba = True
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
                over = True
                break

            page.get(tieba_url)
            if is_first_tieba:
                page.refresh()
                page._wait_loaded(3)
                is_first_tieba = False
            page.wait.eles_loaded('xpath://*[@id="signstar_wrapper"]/a/span[1]', timeout=30)

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
                page.wait.eles_loaded('xpath://a[@class="j_signbtn sign_btn_bright j_cansign"]', timeout=30)
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
