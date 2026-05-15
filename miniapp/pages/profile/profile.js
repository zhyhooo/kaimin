const app = getApp()
Page({
  data: { profile: null, unreadCount: 0 },
  onShow() { this.load() },
  async load() {
    try {
      const res = await app.request({ url: '/profile/' })
      // 同步 memberId
      if (res.member && res.member.id) {
        app.globalData.memberId = res.member.id
        wx.setStorageSync('memberId', res.member.id)
      }
      this.setData({ profile: res, unreadCount: res.unread_messages || 0 })
    } catch (e) {}
  },
  goEdit() { wx.navigateTo({ url: '/pages/profile/edit' }) },
  goMyEvents() { wx.navigateTo({ url: '/pages/event/event' }) },
  goMyInfos() { wx.navigateTo({ url: '/pages/social-sentiment/list' }) },
  goMyScores() { wx.navigateTo({ url: '/pages/scoring/scoring' }) },
  goMessages() { wx.navigateTo({ url: '/pages/profile/messages' }) },
  logout() {
    wx.showModal({
      title: '确认退出',
      success: (res) => {
        if (res.confirm) {
          wx.removeStorageSync('token')
          wx.removeStorageSync('role')
          wx.removeStorageSync('memberId')
          app.globalData.token = null
          app.globalData.role = null
          app.globalData.memberId = null
          this.setData({ profile: null, unreadCount: 0 })
          wx.switchTab({ url: '/pages/index/index' })
        }
      }
    })
  }
})
