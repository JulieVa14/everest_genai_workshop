import { createDarkTheme, createLightTheme } from '@fluentui/react-components';
import type { BrandVariants } from '@fluentui/react-components';

const brand: BrandVariants = {
  10: '#031410', 20: '#082A22', 30: '#0B382D', 40: '#0E4438',
  50: '#115044', 60: '#145E4E', 70: '#176B58', 80: '#1B7C66',
  90: '#278D76', 100: '#3F9E89', 110: '#60AE9D', 120: '#80BFB0',
  130: '#A1D0C3', 140: '#C1E1D7', 150: '#DCEFE9', 160: '#F1F9F6',
};
const fonts = { fontFamilyBase: "'Source Sans 3', sans-serif", fontFamilyNumeric: "'Source Sans 3', sans-serif",
  borderRadiusMedium: '4px', borderRadiusLarge: '8px' };
export const lightTheme = { ...createLightTheme(brand), ...fonts,
  colorBrandBackground: '#176B58', colorBrandForeground1: '#176B58',
  colorNeutralBackground2: '#F6F7F8', colorNeutralForeground1: '#232629',
  colorNeutralForeground2: '#626A70', colorNeutralStroke1: '#D8DEE0' };
export const darkTheme = { ...createDarkTheme(brand), ...fonts };