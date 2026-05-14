const app = getApp()
Page({ data: { venue: null }, onLoad() { this.load() }, async load() { try { const res = await app.request({ url: '/venues/1' }); this.setData({ venue: res }) } catch (e) {} }, goBooking() { wx.navigateTo({ url: '/pages/venue/booking' }) } })
