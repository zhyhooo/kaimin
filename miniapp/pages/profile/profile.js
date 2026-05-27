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
  roleLabel(r) {
    const m = { super_admin: '超级管理员', org_leader: '总支委员', branch_leader: '支部主委', member: '会员', public: '公众' }
    return m[r] || r
  },
  goEdit() { wx.navigateTo({ url: '/pages/profile/edit' }) },
  goMyEvents() { wx.navigateTo({ url: '/pages/event/event' }) },
  goMyInfos() { wx.navigateTo({ url: '/pages/social-sentiment/list' }) },
  goMyScores() { wx.navigateTo({ url: '/pages/scoring/scoring' }) },
  goMessages() { wx.navigateTo({ url: '/pages/profile/messages' }) },
  async onGetPhone(e) {
    if (!e.detail.code) return
    try {
      const res = await app.request({
        url: '/auth/bind-phone',
        method: 'POST',
        data: { code: e.detail.code },
        noAuth: false
      })
      // 更新 token 和角色
      app.globalData.token = res.access_token
      app.globalData.role = res.role
      app.globalData.memberId = res.member_id
      wx.setStorageSync('token', res.access_token)
      wx.setStorageSync('role', res.role)
      if (res.member_id) wx.setStorageSync('memberId', res.member_id)
      wx.showToast({ title: '绑定成功', icon: 'success' })
      this.load()
    } catch (e) {
      wx.showToast({ title: '绑定失败，请重试', icon: 'none' })
    }
  },
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
