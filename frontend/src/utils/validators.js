// 正则表达式
export const REGEX = {
  PHONE: /^1[3-9]\d{9}$/,
  EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/
}

// 验证手机号
export const validatePhone = (phone) => {
  const reg = /^1[3-9]\d{9}$/
  return reg.test(phone)
}

// 验证邮箱
export const validateEmail = (email) => {
  const reg = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return reg.test(email)
}

// 验证密码一致性
export const validatePasswordMatch = (password, confirmPassword) => {
  return password === confirmPassword
}

export const validatePassword = (password) => {
  // 密码至少包含8个字符，至少一个字母和一个数字
  const reg = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$/
  return reg.test(password)
}
