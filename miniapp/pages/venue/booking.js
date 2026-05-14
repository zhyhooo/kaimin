	const app = getApp()
	Page({
	  data: { date: '', slot: '', slotIndex: -1, purpose: '', count: 1, name: '', phone: '', slots: ['上午 9:00-12:00', '下午 14:00-17:00', '晚上 18:00-21:00'] },
	  onFieldChange(e) {
	    const { field } = e.currentTarget.dataset
	    this.setData({ [field]: e.detail.value })
	  },
	  onDateChange(e) {
	    this.setData({ date: e.detail.value })
	  },
	  onSlotChange(e) {
	    const idx = e.detail.value
	    this.setData({ slotIndex: idx, slot: this.data.slots[idx] })
	  },
	  async submit() {
    if (!this.data.date || !this.data.slot || !this.data.purpose || !this.data.name || !this.data.phone) { wx.showToast({ title: '请填写完整信息', icon: 'none' }); return }
    try { await app.request({ url: '/venues/1/book', method: 'POST', data: { venue_id: 1, date: this.data.date, time_slot: this.data.slot, purpose: this.data.purpose, people_count: this.data.count, contact_name: this.data.name, contact_phone: this.data.phone } }); wx.showToast({ title: '预约申请已提交' }); setTimeout(() => wx.navigateBack(), 1500) } catch (e) {}
  }
})
