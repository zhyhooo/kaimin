const app = getApp()

Page({
  data: {
    member: null,
    notices: [],
    recentEvent: null,
    unreadCount: 0,
    isLoggedIn: false
  },

  onShow() {
    this.setData({ isLoggedIn: !!app.globalData.token })
    if (app.globalData.token) {
      this.loadData()
    }
  },

  // 点击登录
  async handleLogin() {
    try {
      wx.showLoading({ title: '登录中...' })
      await app.wxLogin()
      wx.hideLoading()
      wx.showToast({ title: '登录成功', icon: 'success' })
      this.setData({ isLoggedIn: true })
      this.loadData()
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: '登录失败，请重试', icon: 'none' })
    }
  },

  async loadData() {
    try {
      const [profileRes, noticeRes, eventRes] = await Promise.all([
        app.request({ url: '/profile/' }),
        app.request({ url: '/notifications/' }),
        app.request({ url: '/events/' })
      ])

      // 同步 memberId 到 globalData
      if (profileRes.member && profileRes.member.id) {
        app.globalData.memberId = profileRes.member.id
        wx.setStorageSync('memberId', profileRes.member.id)
      }

      this.setData({
        member: profileRes.member,
        notices: (noticeRes || []).slice(0, 3),
        recentEvent: (eventRes || [])[0] || null,
        unreadCount: profileRes.unread_messages || 0
      })
    } catch (e) {
      // 未登录时仅显示公开内容
    }
  },

  goNotice() {
    wx.switchTab({ url: '/pages/notice/notice' })
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/notice/detail?id=${id}` })
  },

  goEvent(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/event/detail?id=${id}` })
  },

  goProfile() {
    wx.switchTab({ url: '/pages/profile/profile' })
  }
})
