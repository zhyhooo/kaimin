App({
  globalData: {
    userInfo: null,
    token: null,
    role: null,
    memberId: null,
    baseUrl: 'https://api.kaimin.org'
  },

  onLaunch() {
    const token = wx.getStorageSync('token')
    const role = wx.getStorageSync('role')
    const memberId = wx.getStorageSync('memberId')
    if (token) {
      this.globalData.token = token
      this.globalData.role = role
      this.globalData.memberId = memberId
    }
  },

  // 微信一键登录
  async wxLogin() {
    return new Promise((resolve, reject) => {
      wx.login({
        success: async (loginRes) => {
          try {
            const res = await this.request({
              url: '/auth/wechat-login',
              method: 'POST',
              data: { code: loginRes.code },
              noAuth: true
            })
            this.globalData.token = res.access_token
            this.globalData.role = res.role
            this.globalData.memberId = res.member_id
            wx.setStorageSync('token', res.access_token)
            wx.setStorageSync('role', res.role)
            if (res.member_id) wx.setStorageSync('memberId', res.member_id)
            resolve(res)
          } catch (err) {
            reject(err)
          }
        },
        fail: reject
      })
    })
  },

  // 全局请求方法
  request(options) {
    const { url, method = 'GET', data, header = {}, noAuth = false } = options
    const self = this
    return new Promise((resolve, reject) => {
      const headers = { 'Content-Type': 'application/json' }
      if (!noAuth && self.globalData.token) {
        headers['Authorization'] = `Bearer ${self.globalData.token}`
      }
      wx.request({
        url: `${self.globalData.baseUrl}${url}`,
        method,
        data,
        header: { ...headers, ...header },
        success(res) {
          if (res.statusCode === 200 || res.statusCode === 201) {
            resolve(res.data)
          } else if (res.statusCode === 401) {
            wx.removeStorageSync('token')
            wx.removeStorageSync('role')
            wx.removeStorageSync('memberId')
            self.globalData.token = null
            self.globalData.role = null
            self.globalData.memberId = null
            wx.showToast({ title: '登录已过期，请重新登录', icon: 'none' })
            reject(res)
          } else {
            const msg = (res.data && res.data.detail) || (res.data && res.data.message) || '请求失败'
            wx.showToast({ title: msg, icon: 'none' })
            reject(res)
          }
        },
        fail(err) {
          wx.showToast({ title: '网络异常，请重试', icon: 'none' })
          reject(err)
        }
      })
    })
  }
})
