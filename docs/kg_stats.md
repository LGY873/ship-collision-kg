## 一、节点规模

| 实体类型 | 节点数 | 占比 | 示例 |
| --- | ---: | ---: | --- |
| Accident | 32 | 13.2% | Allision of Bulk Carrier Herbert C. Jackson with the Jefferson Avenue Bridge、Allision of the ITB Krystal Sea/Cordova Provider With US Coast Guard Cutter Sycamore、Collision between US Fishing Vessel American Dynasty and Canadian Naval Frigate Winnipeg |
| Ship | 72 | 29.8% | Bulk carrier Herbert C. Jackson、Jefferson Avenue Bridge、Integrated tug and barge Krystal Sea/Cordova Provider |
| Person | 34 | 14.0% | bridge tender、mate、captain |
| Organization | 42 | 17.4% | Wayne County Road Commission、Bering Marine Corporation、Lynden Incorporated |
| Environment | 36 | 14.9% | Weather clear with good visibility, air temperature 40°F, southwesterly winds at 17 knots、visibility 0.25 to 4 miles due to patchy, directional fog/low clouds、Weather Clear; good visibility; northeast winds at 3 knots |
| Equipment | 22 | 9.1% | twin azimuthing stern drives (ASD)、CP system、Steering gear pumps |
| Consequence | 4 | 1.7% | $2.2 million est. in damages、Dock, water intakes, the Nordbay sustained an estimated $6.4 million in total damage、property damage $21,338,000 est. |
| **合计** | **242** | 100% | |

## 二、关系规模

| 关系类型 | 边数 | 占比 |
| --- | ---: | ---: |
| crewed_by | 48 | 18.9% |
| caused_by_person | 42 | 16.5% |
| affected_by | 34 | 13.4% |
| operated_by | 29 | 11.4% |
| occurred_at | 27 | 10.6% |
| equipped_with | 21 | 8.3% |
| caused_by_equipment | 15 | 5.9% |
| involved_person | 15 | 5.9% |
| caused_by_org | 11 | 4.3% |
| collided_with | 5 | 2.0% |
| led_to | 4 | 1.6% |
| involves_ship | 3 | 1.2% |
| **合计** | **254** | 100% |

## 三、度分布

| 度区间 | 节点数 | 占比 |
| --- | ---: | ---: |
| 0 | 57 | 23.6% |
| 1 | 72 | 29.8% |
| 2 | 55 | 22.7% |
| 3–5 | 39 | 16.1% |
| 6–10 | 15 | 6.2% |
| 11–20 | 4 | 1.7% |
| ≥21 | 0 | 0.0% |

## 四、中心节点（度 Top）

| 排名 | 节点 | 类型 | 度 |
| ---: | --- | --- | ---: |
| 1 | master | Person | 20 |
| 2 | pilot | Person | 18 |
| 3 | captain | Person | 16 |
| 4 | Contact of Tanker Atina with Oil and Gas Production Platform SP-57B | Accident | 13 |
| 5 | DCA18FM023 | Accident | 10 |
| 6 | Contact of Savage Voyager Tow with Jamie Whitten Lock & Dam | Accident | 10 |
| 7 | Collision Between Liquefied Petroleum Gas Carrier Gas Ares and Moored Tug Sabine | Accident | 9 |
| 8 | mate | Person | 8 |
| 9 | Visibility 10 miles | Environment | 8 |
| 10 | DCA16FM003 | Accident | 8 |
| 11 | DCA16FM018 | Accident | 7 |
| 12 | Leviticus | Ship | 7 |
| 13 | Tanker Atina | Ship | 7 |
| 14 | Deckhand | Person | 6 |
| 15 | DCA16FM033 | Accident | 6 |

## 五、跨文档合并

出现在 2 篇及以上的节点：**15** 个（占 6.2%）

| 节点 | 类型 | 文档数 |
| --- | --- | ---: |
| pilot | Person | 14 |
| master | Person | 12 |
| captain | Person | 11 |
| Visibility 10 miles | Environment | 7 |
| mate | Person | 5 |
| US Coast Guard | Organization | 5 |
| Deckhand | Person | 5 |
| navigation | Equipment | 4 |
| helmsman | Person | 3 |
| engineer | Person | 3 |

## 六、事故覆盖

事故节点 32 个；有关系输出的事故 32 个

## 七、属性完整度

| 实体类型 | 属性非空率 | 主要属性 |
| --- | ---: | --- |
| Accident | 100% | accident_no、type、date、location |
| Ship | 100% | status、ship_type、name、flag |
| Person | 100% | role、name、license、experience_years |
| Organization | 100% | org_type、name、role |
| Environment | 100% | category、description、unit、value |
| Equipment | 100% | category、name |
| Consequence | 100% | type、value、unit |
