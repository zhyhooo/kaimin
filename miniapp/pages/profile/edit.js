const app = getApp()
Page({
  data: { form: {} },
  onLoad() { this.loadProfile() },
  async loadProfile() {
    try { const res = await app.request({ url: '/profile/' }); this.setData({ form: { phone: res.member?.work_unit ? '' : '', work_unit: res.member?.work_unit || '', work_position: res.member?.work_position || '', title: res.member?.title || '', education: res.member?.education || '', school: res.member?.school || '', specialty: res.member?.specialty || '', social_position: res.member?.social_position || '' } }) } catch (e) {}
  },
  onFieldChange(e) { const { field } = e.currentTarget.dataset; this.setData({ [`form.${field}`]: e.detail.value }) },
  async submit() { try { await app.request({ url: `/members/${getApp().globalData.memberId}`, method: 'PUT', data: this.data.form }); wx.showToast({ title: '提交成功，等待审核' }); wx.navigateBack() } catch (e) {} }
})
