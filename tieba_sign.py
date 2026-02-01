from DrissionPage import ChromiumOptions, ChromiumPage
import json
import os
import shutil
import time
import requests

def read_cookie():
    """读取 cookie，优先从环境变量读取"""
    if "TIEBA_COOKIES" in os.environ:
        try:
            return json.loads(os.environ["TIEBA_COOKIES"])
        except Exception as e:
            print(f"Cookie解析失败：{e}")
            return []
    else:
        print("贴吧Cookie未配置！详细请参考教程！")
        return []

def get_level_exp(page):
    """获取等级和经验，兼容不同页面结构"""
    level, exp = "未知", "未知"
    level_eles = [
        '//*[@id="pagelet_aside/pagelet/my_tieba"]/div/div[1]/div[3]/div[1]/a/div[2]',
        '//div[contains(@class,"user-level")]/span'
    ]
    exp_eles = [
        '//*[@id="pagelet_aside/pagelet/my_tieba"]/div/div[1]/div[3]/div[2]/a/div[2]/span[1]',
        '//div[contains(@class,"user-exp")]/span[1]'
    ]
    for ele_xpath in level_eles:
        try:
            level_ele = page.ele(xpath=ele_xpath)
            if level_ele:
                level = level_ele.text.strip()
                break
        except:
            continue
    for ele_xpath in exp_eles:
        try:
            exp_ele = page.ele(xpath=ele_xpath)
            if exp_ele:
                exp = exp_ele.text.strip()
                break
        except:
            continue
    return level, exp

def send_tieba_comment(page, post_url, comment_content):
    """
    贴吧指定帖子发评论
    page: 浏览器页面对象
    post_url: 目标帖子完整链接
    comment_content: 要发送的评论内容
    return: 评论结果消息
    """
    try:
        # 打开目标帖子
        page.get(post_url)
        page.wait.loaded(timeout=20)
        time.sleep(1)  # 缓冲加载

        # 1. 定位评论输入框
        comment_input = page.ele(xpath='//textarea[@id="ueditor_replace"]', timeout=10)
        if not comment_input:
            comment_input = page.ele(xpath='//textarea[contains(@class,"comment-input")]', timeout=5)
        if not comment_input:
            return "失败：未找到评论输入框（页面结构可能更新）"

        # 2. 输入评论内容
        comment_input.input(comment_content)
        time.sleep(0.8)  # 避免输入过快

        # 3. 定位并点击发送按钮
        send_btn = page.ele(xpath='//button[contains(text(),"发表")]', timeout=10)
        if not send_btn:
            send_btn = page.ele(xpath='//input[@value="发表回复" or @value="发表评论"]', timeout=5)
        if not send_btn:
            return "失败：未找到发表按钮"

        send_btn.click()
        time.sleep(2)  # 等待发送请求完成

        # 4. 校验是否发送成功（判断提示）
        success_msg = page.ele(xpath='//div[contains(text(),"回复成功") or contains(text(),"评论成功")]', timeout=5)
        error_msg = page.ele(xpath='//div[contains(text(),"失败") or contains(text(),"请登录") or contains(text(),"违规")]', timeout=3)
        
        if success_msg:
            return f"成功：评论已发送，内容【{comment_content}】"
        elif error_msg:
            return f"失败：{error_msg.text.strip()}"
        else:
            return "成功：评论提交（无明确提示，大概率发送成功）"

    except Exception as e:
        return f"异常失败：{str(e)}"

if __name__ == "__main__":
    print("程序开始运行")
    notice = ''
    co = ChromiumOptions().headless()

    chromium_path = shutil.which("chromium-browser") or shutil.which("chrome") or shutil.which("msedge")
    if chromium_path:
        co.set_browser_path(chromium_path)

    page = ChromiumPage(co)
    url = "https://tieba.baidu.com/"
    
    page.get(url)
    cookies = read_cookie()
    if cookies:
        page.set.cookies(cookies)
        page.refresh()
    page.wait.loaded(timeout=15)

    over = False
    yeshu = 0
    count = 0

    while not over:
        yeshu += 1
        forum_url = f"https://tieba.baidu.com/i/i/forum?pn={yeshu}"
        page.get(forum_url)
        page.wait.loaded(timeout=15)

        for i in range(1, 21):
            ele_xpath = f'//*[@id="like_pagelet"]/div[1]/div[1]/table/tbody/tr[{i}]/td[1]/a'
            element = page.ele(xpath=ele_xpath)
            if not element:
                break

            try:
                tieba_url = element.attr("href")
                name = element.attr("title").strip() if element.attr("title") else f"未知贴吧{i}"
                if not tieba_url.startswith("http"):
                    tieba_url = f"https://tieba.baidu.com{tieba_url}"
            except Exception as e:
                print(f"获取贴吧链接失败：{e}")
                continue

            try:
                page.get(tieba_url)
                page.wait.loaded(timeout=20)

                # 签到状态判断
                sign_wrapper = page.ele(xpath='//*[@id="signstar_wrapper"]/a/span[1]', timeout=10)
                if not sign_wrapper:
                    msg = f"{name}吧：页面无签到模块，跳过"
                    print(msg)
                    notice += msg + '\n\n'
                    count +=1
                    page.back()
                    time.sleep(0.5)  # 降低访问频率，避免风控
                    print("-------------------------------------------------")
                    continue

                is_sign_text = sign_wrapper.text.strip()
                # 已签到判断
                if any(key in is_sign_text for key in ["连续", "已签到", "天"]):
                    level, exp = get_level_exp(page)
                    msg = f"{name}吧：已签到！等级：{level}，经验：{exp}"
                    print(msg)
                    notice += msg + '\n\n'
                else:  # 未签到，执行签到
                    sign_btn = page.ele(xpath='//a[contains(@class,"j_signbtn") and contains(@class,"j_cansign")]', timeout=10)
                    if sign_btn:
                        sign_btn.click()
                        time.sleep(1.5)  # 延长等待，确保签到请求发送
                        page.refresh()
                        page.wait.loaded(timeout=10)
                        # 签到后校验
                        new_sign_text = page.ele('//*[@id="signstar_wrapper"]/a/span[1]').text.strip()
                        level, exp = get_level_exp(page)
                        if any(key in new_sign_text for key in ["连续", "已签到"]):
                            msg = f"{name}吧：签到成功！等级：{level}，经验：{exp}"
                        else:
                            msg = f"{name}吧：签到触发验证，需手动处理！"
                    else:
                        msg = f"{name}吧：无可用签到按钮（可能需验证/权限不足）"
                    print(msg)
                    notice += msg + '\n\n'
                
                count +=1
                page.back()
                page.wait.loaded(timeout=10)
                time.sleep(0.5)  # 防反爬
                print("-------------------------------------------------")
            except Exception as e:
                msg = f"{name}吧：签到异常 - {str(e)}"
                print(msg)
                notice += msg + '\n\n'
                count +=1
                page.back()
                time.sleep(1)
                print("-------------------------------------------------")
                continue

        # 分页判断
        if i < 19:
            over = True
            msg = f"全部爬取完成！本次共处理 {count} 个吧"
            print(msg)
            notice += msg + '\n\n'

    page.quit()  # 彻底关闭浏览器，释放资源
    
    # 指定帖子评论
    target_post_url = "https://tieba.baidu.com/p/9983496041"
    my_comment = "3"
    if cookies:
        comment_page = ChromiumPage(co)
        comment_page.get("https://tieba.baidu.com/")
        comment_page.set.cookies(cookies)
        comment_page.refresh()
        for i in range(1, 5):
            print(f"执行第{i}次评论")
            comment_result = send_tieba_comment(comment_page, target_post_url, my_comment)
            print(f"第{i}次评论结果：{comment_result}")
            notice += f"第{i}次：{comment_result}\n"
            # 间隔8秒，避免被风控
            if i < 4:
                time.sleep(8) 
        comment_page.quit()
    else:
        no_comment_msg = "未执行评论：Cookie未配置/未登录"
        print(no_comment_msg)
        notice += f"\n{no_comment_msg}"

    # Server酱通知
    if "SendKey" in os.environ:
        api = f'https://sc.ftqq.com/{os.environ["SendKey"]}.send'
        title = "贴吧签到信息"
        data = {"text": title, "desp": notice}
        try:
            req = requests.post(api, data=data, timeout=60)
            if req.status_code == 200:
                print("Server酱通知发送成功")
            else:
                print(f"通知失败，状态码：{req.status_code}")
        except Exception as e:
            print(f"通知发送异常：{e}")
    else:
        print("未配置Server酱服务，跳过通知")
