const app = getApp()
Page({
  data: { form: {} },
  onLoad() { this.loadProfile() },
  async loadProfile() {
    try {
      const res = await app.request({ url: '/profile/' })
      const m = res.member || {}
      // 同步 memberId
      if (m.id) {
        app.globalData.memberId = m.id
        wx.setStorageSync('memberId', m.id)
      }
      this.setData({
        form: {
          work_unit: m.work_unit || '',
          work_position: m.work_position || '',
          title: m.title || '',
          education: m.education || '',
          school: m.school || '',
          specialty: m.specialty || '',
          social_position: m.social_position || ''
        }
      })
    } catch (e) {}
  },
  onFieldChange(e) {
    const { field } = e.currentTarget.dataset
    this.setData({ [`form.${field}`]: e.detail.value })
  },
  async submit() {
    const mid = app.globalData.memberId
    if (!mid) {
      wx.showToast({ title: '请先登录', icon: 'none' })
      return
    }
    try {
      await app.request({ url: `/members/${mid}`, method: 'PUT', data: this.data.form })
      wx.showToast({ title: '保存成功' })
      wx.navigateBack()
    } catch (e) {}
  }
})
