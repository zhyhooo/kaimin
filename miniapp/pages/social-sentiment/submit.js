	const app = getApp()
	Page({
	  data: { title: '', content: '', isJoint: false },
	  onFieldChange(e) {
	    const { field } = e.currentTarget.dataset
	    this.setData({ [field]: e.detail.value })
	  },
	  onSwitchChange(e) {
	    this.setData({ isJoint: e.detail.value })
	  },
	  async submit() {
    if (!this.data.title || !this.data.content) { wx.showToast({ title: '标题和正文为必填', icon: 'none' }); return }
    try {
      await app.request({ url: '/social-info/', method: 'POST', data: { title: this.data.title, is_joint: this.data.isJoint, content: this.data.content } })
      wx.showToast({ title: '提交成功' }); setTimeout(() => wx.navigateBack(), 1500)
    } catch (e) {}
  }
})
