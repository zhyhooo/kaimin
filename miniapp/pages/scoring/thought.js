const app = getApp()
Page({
  data: { content: '', attachment: '' },
  onFieldChange(e) {
    const { field } = e.currentTarget.dataset
    this.setData({ [field]: e.detail.value })
  },
  async submit() {
    const mid = app.globalData.memberId
    if (!mid) {
      wx.showToast({ title: '请先登录', icon: 'none' })
      return
    }
    if (!this.data.content.trim()) {
      wx.showToast({ title: '请输入思想汇报内容', icon: 'none' })
      return
    }
    try {
      await app.request({
        url: `/scoring/candidate/${mid}/thought-report`,
        method: 'POST',
        data: {
          content: this.data.content,
          attachment_url: this.data.attachment || null
        }
      })
      wx.showToast({ title: '提交成功，已自动记分', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 1500)
    } catch (e) {}
  }
})