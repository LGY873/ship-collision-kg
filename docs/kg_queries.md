# 图谱分析查询结果

节点 242 个、边 254 条。

### q1 高频致因因素（按事故数去重）

| 因素类型 | 因素 | 关系 | 事故数 | 边数 |
|---|---|---|---|---|
| Person | master | caused_by_person | 9 | 9 |
| Person | pilot | caused_by_person | 9 | 9 |
| Person | captain | caused_by_person | 6 | 6 |
| Environment | Visibility 10 miles | affected_by | 5 | 5 |
| Person | mate | caused_by_person | 3 | 3 |
| Environment | Weather clear with good visibility, air temperature 40°F, southwesterly winds at | affected_by | 1 | 1 |
| Organization | Wayne County Road Commission | caused_by_org | 1 | 1 |
| Environment | visibility 0.25 to 4 miles due to patchy, directional fog/low clouds | affected_by | 1 | 1 |
| Equipment | twin azimuthing stern drives (ASD) | caused_by_equipment | 1 | 1 |
| Equipment | CP system | caused_by_equipment | 1 | 1 |
| Environment | Visibility 10 miles, Wind north 13.8 knots, overcast sky, light rain, light fog, | affected_by | 1 | 1 |
| Equipment | Steering gear pumps | caused_by_equipment | 1 | 1 |
| Environment | Light wind, calm seas, restricted visibility due to fog. | affected_by | 1 | 1 |
| Equipment | starboard engine throttle | caused_by_equipment | 1 | 1 |
| Environment | current 1.5 knots | affected_by | 1 | 1 |
| Person | officer of the watch (third mate) | caused_by_person | 1 | 1 |
| Equipment | navigation | caused_by_equipment | 1 | 1 |
| Equipment | propulsion | caused_by_equipment | 1 | 1 |
| Equipment | bow thruster | caused_by_equipment | 1 | 1 |
| Environment | visibility 10 miles, winds 13 mph with gusts to 23 mph from the southwest, air t | affected_by | 1 | 1 |

### q2 因素共现对（叠加风险组合）

| 因素 1 | 类型 1 | 因素 2 | 类型 2 | 共现事故数 |
|---|---|---|---|---|
| master | Person | pilot | Person | 6 |
| captain | Person | mate | Person | 3 |
| Visibility 10 miles | Environment | master | Person | 2 |
| captain | Person | pilot | Person | 2 |
| Wayne County Road Commission | Organization | Weather clear with good visibility, air temperature 40°F, southwesterly winds at | Environment | 1 |
| captain | Person | twin azimuthing stern drives (ASD) | Equipment | 1 |
| captain | Person | visibility 0.25 to 4 miles due to patchy, directional fog/low clouds | Environment | 1 |
| twin azimuthing stern drives (ASD) | Equipment | visibility 0.25 to 4 miles due to patchy, directional fog/low clouds | Environment | 1 |
| CP system | Equipment | Visibility 10 miles | Environment | 1 |
| CP system | Equipment | master | Person | 1 |
| Steering gear pumps | Equipment | Visibility 10 miles, Wind north 13.8 knots, overcast sky, light rain, light fog, | Environment | 1 |
| Light wind, calm seas, restricted visibility due to fog. | Environment | captain | Person | 1 |
| Light wind, calm seas, restricted visibility due to fog. | Environment | mate | Person | 1 |
| Light wind, calm seas, restricted visibility due to fog. | Environment | starboard engine throttle | Equipment | 1 |
| captain | Person | starboard engine throttle | Equipment | 1 |
| mate | Person | starboard engine throttle | Equipment | 1 |
| bow thruster | Equipment | current 1.5 knots | Environment | 1 |
| bow thruster | Equipment | master | Person | 1 |
| bow thruster | Equipment | navigation | Equipment | 1 |
| bow thruster | Equipment | officer of the watch (third mate) | Person | 1 |

### q3 国别 × 关系分布

| 国别 | 关系 | 边数 |
|---|---|---|
| US | caused_by_person | 42 |
| US | affected_by | 34 |
| US | occurred_at | 27 |
| US | caused_by_equipment | 15 |
| US | involved_person | 15 |
| US | caused_by_org | 11 |
| US | led_to | 4 |
| US | involves_ship | 3 |

### q4 船型—事故类型关联（involves_ship 边）

| 船型 | 事故类型 | 事故数 |
|---|---|---|
| tugboat | collision | 2 |
| cargo vessel | collision | 1 |

### q5 时间趋势

| 年份 | 事故数 | 后果数 |
|---|---|---|
| 2007 | 2 | 1 |
| 2013 | 3 | 0 |
| 2014 | 1 | 0 |
| 2015 | 2 | 0 |
| 2016 | 2 | 1 |
| 2017 | 2 | 0 |
| 2018 | 1 | 0 |
| 2019 | 2 | 0 |
| 2020 | 3 | 0 |
| 2021 | 2 | 0 |
| 2022 | 4 | 0 |
| 2023 | 1 | 0 |
| 2024 | 1 | 0 |

### q6 节点中心性（度）

| 类型 | 节点 | 度 |
|---|---|---|
| Person | master | 20 |
| Person | pilot | 18 |
| Person | captain | 16 |
| Person | mate | 8 |
| Environment | Visibility 10 miles | 8 |
| Ship | Leviticus | 7 |
| Ship | Tanker Atina | 7 |
| Person | Deckhand | 6 |
| Ship | CG 29113 | 6 |
| Ship | Tugboat George M | 6 |
| Ship | Tristan Janice | 5 |
| Ship | Nordbay | 5 |
| Ship | Mia S | 5 |
| Ship | Danny Terral | 5 |
| Ship | Towing vessel Bayou Lady | 4 |
| Equipment | navigation | 4 |
| Organization | US Coast Guard | 4 |
| Ship | Manizales | 4 |
| Ship | Specialist | 4 |
| Person | tankerman | 4 |

### q7 因素—后果传导（同事故共现）

| 因素 | 后果 | 事故数 |
|---|---|---|
| Overcast, winds 22 mph gusting to 28 mph, air temperature 45oF, relative humidit | $2.2 million est. in damages | 1 |
| New Orleans-Baton Rouge Pilots Association (NOBRA) | $2.2 million est. in damages | 1 |
| The Mississippi River has a project depth of 45 feet from Southwest Pass, near t | $2.2 million est. in damages | 1 |
| master | $2.2 million est. in damages | 1 |
| pilot | $2.2 million est. in damages | 1 |
| pilot | Dock, water intakes, the Nordbay sustained an estimated $6.4 million in total da | 1 |
| master | Dock, water intakes, the Nordbay sustained an estimated $6.4 million in total da | 1 |
| Visibility 8 miles, south winds at 17–24 knots, air temperature 73°F, water temp | Dock, water intakes, the Nordbay sustained an estimated $6.4 million in total da | 1 |
| pilot | property damage $21,338,000 est. | 1 |
| master | property damage $21,338,000 est. | 1 |
| visibility, winds southeast <10 knots, slack current, air temperature 77°F, wate | property damage $21,338,000 est. | 1 |
| steering | property damage $21,338,000 est. | 1 |
| Visibility 10 miles | Damage | 1 |

### q8 单事故子图：Allision of Bulk Carrier Herbert C. Jackson with the Jeffers

| 邻居类型 | 邻居 | 关系 | 来源文档 | 证据句 |
|---|---|---|---|---|
| Environment | Weather clear with good visibility, air temperature 40°F, southwesterly winds at | affected_by | us_DCA13LM021 | Weather clear with good visibility, air temperature 40°F, southwesterly winds at |
| Organization | Wayne County Road Commission | caused_by_org | us_DCA13LM021 | The bridge tender’s blood alcohol level was found to exceed the legal limit. She |
| Environment | Weather clear with good visibility, air temperature 40°F, southwesterly winds at | occurred_at | us_DCA13LM021 | Weather clear with good visibility, air temperature 40°F, southwesterly winds at |
