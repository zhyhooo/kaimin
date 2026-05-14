const app = getApp()
Page({
  data: { profile: null, unreadCount: 0 },
  onShow() { this.load() },
  async load() {
    try { const res = await app.request({ url: '/profile/' }); this.setData({ profile: res, unreadCount: res.unread_messages || 0 }) } catch (e) {}
  },
  goEdit() { wx.navigateTo({ url: '/pages/profile/edit' }) },
  goMyEvents() { wx.navigateTo({ url: '/pages/event/event' }) },
  goMyInfos() { wx.navigateTo({ url: '/pages/social-sentiment/list' }) },
  goMyScores() { wx.navigateTo({ url: '/pages/scoring/scoring' }) },
  goMessages() { wx.navigateTo({ url: '/pages/profile/messages' }) }
})
