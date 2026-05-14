const app = getApp()

Page({
  data: {
    member: null,
    notices: [],
    recentEvent: null,
    unreadCount: 0
  },

  onShow() {
    this.loadData()
  },

  async loadData() {
    try {
      const [profileRes, noticeRes, eventRes] = await Promise.all([
        app.request({ url: '/profile/' }),
        app.request({ url: '/notifications/' }),
        app.request({ url: '/events/' })
      ])

      this.setData({
        member: profileRes.member,
        notices: (noticeRes || []).slice(0, 3),
        recentEvent: (eventRes || [])[0] || null,
        unreadCount: profileRes.unread_messages || 0
      })
    } catch (e) {
      // 未登录时显示公开内容
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
